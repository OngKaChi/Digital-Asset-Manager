import json
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook, load_workbook
from auditlog.models import LogEntry

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes
VALID_ROLES = {"superadmin", "admin", "editor", "viewer"}

def _rate_limit_key(request, email):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"login_attempts:{ip}:{email}"

def _user_payload(user):
    group_names = list(user.groups.values_list("name", flat=True))
    role = (
        "superadmin"
        if user.is_superuser or "superadmin" in group_names
        else (group_names[0] if group_names else None)
    )
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email,
        "role": role,
        "is_superuser": user.is_superuser,
    }


def _is_admin(user):
    return (user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name__in=["admin", "superadmin"]).exists()))


# Login Function
@csrf_exempt
@require_POST
def login_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    remember_me = bool(payload.get("rememberMe"))

    if not email or not password:
        return JsonResponse({"detail": "Email and password are required."}, status=400)

    key = _rate_limit_key(request, email)
    attempts = cache.get(key, 0)

    if attempts >= MAX_ATTEMPTS:
        return JsonResponse(
            {"detail": "Too many login attempts. Try again later."},
            status=429,
        )

    UserModel = get_user_model()
    users = list(UserModel.objects.filter(email__iexact=email)[:2])

    # Unified response for "no user" / "wrong password" / "inactive" / "duplicate email"
    # to prevent account enumeration via differing status codes/messages.
    generic_error = JsonResponse({"detail": "Invalid credentials."}, status=401)

    if not users or len(users) > 1:
        cache.set(key, attempts + 1, LOCKOUT_SECONDS)
        return generic_error

    user = users[0]

    if not user.is_active or not user.check_password(password):
        cache.set(key, attempts + 1, LOCKOUT_SECONDS)
        
        # Log the failed login attempt for audit purposes
        LogEntry.objects.log_create(
            instance = user,
            action = LogEntry.Action.ACCESS,
            actor = None,
            remote_addr = request.META.get('REMOTE_ADDR', 'unknown'),
            additional_data = {
                'message': 'User login failed.',
                'email': email,
                'reason': 'Inactive account' if not user.is_active else 'Incorrect password'
            },
            force_log=True  # Ensure this log entry is created even if the user is inactive
        )
        return generic_error

    # Success — clear the counter
    cache.delete(key)

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    
    # Log the successful login attempt for audit purposes
    LogEntry.objects.log_create(
        instance = user,
        action = LogEntry.Action.ACCESS,
        actor = user,
        remote_addr = request.META.get('REMOTE_ADDR', 'unknown'),
        additional_data = {
            'message': 'User login successful.',
            'email': email,
        },
        force_log=True  # Ensure this log entry is created even if the user is inactive
    )
    
    if remember_me:
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
    else:
        request.session.set_expiry(0)  # Browser session

    return JsonResponse({"user": _user_payload(user)})

@csrf_exempt
@require_POST
def forgot_password_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    email = (payload.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"detail": "Email is required."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"detail": "Enter a valid email address."}, status=400)

    key = f"password_reset:{request.META.get('REMOTE_ADDR', 'unknown')}"
    attempts = cache.get(key, 0)
    if attempts >= MAX_ATTEMPTS:
        return JsonResponse(
            {"detail": "Too many reset requests. Try again later."},
            status=429,
        )
    cache.set(key, attempts + 1, LOCKOUT_SECONDS)

    UserModel = get_user_model()
    users = UserModel.objects.filter(email__iexact=email, is_active=True)[:2]
    user_list = list(users)
    if len(user_list) == 1:
        user = user_list[0]
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = (
            f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"
            f"?uid={uid}&token={token}"
        )
        send_mail(
            "Reset your password",
            f"Use the following link to reset your password. "
            f"This link expires in ten minutes:\n\n{reset_url}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

    return JsonResponse({
        "detail": "If an account with that email exists, a password reset link has been sent."
    })


@csrf_exempt
@require_POST
def reset_password_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    uid = payload.get("uid")
    token = payload.get("token")
    password = payload.get("password")
    if not all(isinstance(value, str) and value for value in (uid, token, password)):
        return JsonResponse(
            {"detail": "Reset link and new password are required."},
            status=400,
        )

    UserModel = get_user_model()
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = UserModel.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
        return JsonResponse({"detail": "This reset link is invalid or expired."}, status=400)

    if not default_token_generator.check_token(user, token):
        return JsonResponse({"detail": "This reset link is invalid or expired."}, status=400)

    try:
        validate_password(password, user=user)
    except ValidationError as error:
        return JsonResponse({"detail": error.messages}, status=400)

    user.set_password(password)
    user.save(update_fields=["password"])
    return JsonResponse({"detail": "Your password has been reset. You can now sign in."})

# User List display Function
@csrf_exempt
@require_GET
def user_list_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated."}, status=401)

    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    UserModel = get_user_model()
    users = UserModel.objects.all()
    user_list = [_user_payload(user) for user in users]

    return JsonResponse({"users": user_list})


# Logout Function
@csrf_exempt
@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        LogEntry.objects.log_create(
            instance=request.user,
            action=LogEntry.Action.ACCESS,
            actor=request.user,
            remote_addr=request.META.get("REMOTE_ADDR"),
            additional_data={
                "email": request.user.email,
                "message": "User logged out."},
            force_log=True,
        )
    logout(request)
    return JsonResponse({"success": True})


# Retrieve Current User information Function
@require_GET
def current_user_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated."}, status=401)

    return JsonResponse({"user": _user_payload(request.user)})

@require_GET
def user_audit_log_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    if not request.user.groups.filter(name__in=["superadmin", "admin"]).exists():
        return JsonResponse({"detail": "Not authorized."}, status=403)

    cutoff = timezone.now() - timedelta(days=365)
    LogEntry.objects.filter(timestamp__lt=cutoff).delete()
    logs = LogEntry.objects.filter(timestamp__gte=cutoff).select_related(
        "actor", "content_type"
    )
    events = []
    for entry in logs[:100]:
        additional_data = entry.additional_data or {}
        changes = entry.changes if isinstance(entry.changes, dict) else {}
        events.append({
            "id": entry.pk,
            "actor": (
                entry.actor.get_username()
                if entry.actor_id
                else "Unauthenticated"
            ),
            "subject": entry.object_repr,
            "action": str(entry.get_action_display()),
            "created_at": entry.timestamp.isoformat(),
            "message": additional_data.get("message", ""),
            "reason": additional_data.get("reason", ""),
            "changed_fields": list(changes),
        })

    return JsonResponse({"events": events, "total": logs.count()})


# Create New User Function
@csrf_exempt
@require_POST
def create_user_view(request):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    #make sure the JSON payload is an object
    if not isinstance(payload, dict):
        return JsonResponse(
            {"detail": "Invalid request format."},
            status=400
        )

    #make sure the submitted fields contain strings
    for field in ("username", "email", "password", "role"):
        if field in payload and not isinstance(payload[field], str):
            return JsonResponse(
                {"detail": f"{field.capitalize()} must be text."},
                status=400
            )

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    role = (payload.get("role") or "").strip().lower()

    if not username or not email or not password or role not in VALID_ROLES:
        return JsonResponse({"detail": "Username, email, password, and valid role are required."}, status=400)
    #only the super admins can create admin accounts
    if role == "admin" and not request.user.is_superuser:
        return JsonResponse(
            {"detail": "Only Super Admins can create Admin accounts."},status=403)


    #validate email format before creating the user
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse(
            {"detail": "Please enter a valid email address."},
            status=400
        )

    UserModel = get_user_model()

    #validate username using django's model field rules
    try:
        UserModel._meta.get_field("username").run_validators(username)
    except ValidationError:
        return JsonResponse({"detail": "Invalid username. Check the characters and length."},status=400)

    #check if the username already exists
    if UserModel.objects.filter(username__iexact=username).exists():
        return JsonResponse({"detail": "Username already in use."},status=409)

    #check email if already exists or not
    if UserModel.objects.filter(email__iexact=email).exists():
        return JsonResponse({"detail": "Email already in use."}, status=409)

    try:
        validate_password(password)
    except ValidationError as e:
        return JsonResponse({"detail": e.messages}, status=400)

    try:
        group = Group.objects.get(name=role)
    except Group.DoesNotExist:
        return JsonResponse({"detail": f"Role '{role}' does not exist."}, status=400)

    #user = UserModel.objects.create_user(username=username, email=email, password=password)
    #user.groups.add(group)
    #user.save()
    #return JsonResponse({"user": _user_payload(user)}, status=201)

    #create the user and assign their role as one transaction
    try:
        with transaction.atomic():
            user = UserModel.objects.create_user(
                username=username,email=email,password=password)
            user.groups.add(group)

    except IntegrityError:
        return JsonResponse(
            {"detail": "Account could not be created due to a data conflict."},status=409)

    return JsonResponse({"user": _user_payload(user)}, status=201)

#update the user function
@csrf_exempt
@require_POST
def update_user_view(request, user_id):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    # Ensure the JSON payload is an object
    if not isinstance(payload, dict):
        return JsonResponse(
            {"detail": "Invalid request format."},
            status=400
        )

    # Validate required field types
    for field in ("username", "email", "role"):
        if field in payload and not isinstance(payload[field], str):
            return JsonResponse(
                {"detail": f"{field.capitalize()} must be text."},
                status=400
            )

    # Password is optional, but must be text if provided
    if (
        "password" in payload
        and payload["password"] is not None
        and not isinstance(payload["password"], str)
    ):
        return JsonResponse(
            {"detail": "Password must be text."},
            status=400
        )


    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password")
    role = (payload.get("role") or "").strip().lower()

    if not username or not email or role not in VALID_ROLES:
        return JsonResponse({"detail": "Username, email, and valid role are required."}, status=400)

    #validate email format before updating the user
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse(
            {"detail": "Please enter a valid email address."},
            status=400
        )


    UserModel = get_user_model()

    #validate username before updating the user
    try:
        UserModel._meta.get_field("username").run_validators(username)
    except ValidationError:
        return JsonResponse(
            {"detail": "Invalid username. Check the characters and length."},
            status=400
        )

    try:
        user = UserModel.objects.get(id=user_id)
    except UserModel.DoesNotExist:
        return JsonResponse({"detail": "User not found."}, status=404)

    #protect super admin accounts from being edited
    if user.is_superuser:
        return JsonResponse({"detail": "Super Admin accounts cannot be edited here."},status=403)

    #only super admins can edit the regular admin accounts
    if user.groups.filter(name="admin").exists() and not request.user.is_superuser:
        return JsonResponse({"detail": "Only Super Admins can edit Admin accounts."},status=403)

    #only super admins can promote users to admin level
    if role == "admin" and not request.user.is_superuser:
        return JsonResponse({"detail": "Only Super Admins can assign the Admin role."},status=403)

    #check whether another user already have this username or not
    if UserModel.objects.filter(username__iexact=username).exclude(id=user_id).exists():
        return JsonResponse({"detail": "Username already in use."},status=409)

    if UserModel.objects.filter(email__iexact=email).exclude(id=user_id).exists():
        return JsonResponse({"detail": "Email already in use."}, status=409)

    try:
        group = Group.objects.get(name=role)
    except Group.DoesNotExist:
        return JsonResponse({"detail": f"Role '{role}' does not exist."}, status=400)

    user.username = username
    user.email = email
    if password:
        try:
            validate_password(password, user=user)
        except ValidationError as e:
            return JsonResponse({"detail": e.messages}, status=400)
        user.set_password(password)

    user.groups.clear()
    user.groups.add(group)
    user.save()

    return JsonResponse({"user": _user_payload(user)})


# Delete User Function
@csrf_exempt
@require_POST
def delete_user_view(request, user_id):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    UserModel = get_user_model()
    try:
        user = UserModel.objects.get(id=user_id)
    except UserModel.DoesNotExist:
        return JsonResponse({"detail": "User not found."}, status=404)

    #if user.groups.filter(name="admin").exists():
    #    return JsonResponse({"detail": "Administrator accounts cannot be deleted."}, status=403)

    #protect super admin accs from deletion
    if user.is_superuser:
        return JsonResponse({"detail": "Super Admin accounts cannot be deleted here."},status=403)

    #only super admins can delete admin accounts
    if user.groups.filter(name="admin").exists() and not request.user.is_superuser:
        return JsonResponse({"detail": "Only Super Admins can delete Admin accounts."},status=403)

    user.delete()
    return JsonResponse({"success": True})


@csrf_exempt
@require_GET
def user_import_sample_view(request):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    wb = Workbook()
    ws = wb.active
    ws.title = "Users"
    ws.append(["username", "email", "password", "role"])
    ws.append(["testing", "testing@example.com", "Ch4ngeMe!2024", "viewer"])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="User_import_sample.xlsx"'
    return response


@csrf_exempt
@require_POST
def bulk_import_users_view(request):
    if not _is_admin(request.user):
        return JsonResponse({"detail": "Not authorized."}, status=403)

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"detail": "File required."}, status=400)

    #excel 7 MB
    MAX_IMPORT_SIZE = 7 * 1024 * 1024

    if upload.size > MAX_IMPORT_SIZE:
        return JsonResponse(
            {"detail": "Excel file is too large. Maximum size is 7 MB."},
            status=413
        )


    try:
        wb = load_workbook(upload, data_only=True)
    except Exception:
        return JsonResponse({"detail": "Could not read the uploaded file. Make sure it is a valid .xlsx file."}, status=400)
    ws = wb.active

    required = ["username", "email", "password", "role"]
    header_row = next(ws.rows, None)
    headers = [str(cell.value or "").strip().lower() for cell in header_row] if header_row else []
    if headers != required:
        return JsonResponse({"detail": f"Expected header row {required}."}, status=400)
    #limit excel import to 1000 user records
    MAX_IMPORT_ROWS = 1000
    #subtract 1, first row contains column headers
    if ws.max_row - 1 > MAX_IMPORT_ROWS:
        return JsonResponse(
            {"detail": "Excel import cannot exceed 1000 user records."},status=400)


    User = get_user_model()
    role_groups = {group.name.lower(): group for group in Group.objects.filter(name__in=["admin", "editor", "viewer"])}
    created, skipped_existing, skipped_invalid = [], [], []
    seen = set()
    with transaction.atomic():
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            #make sure the excel cells contain text or empty
            if any(cell is not None and not isinstance(cell, str) for cell in row):
                skipped_invalid.append({
                    "row": idx,
                    "reason": "All user fields must be text"
                })
                continue
            username_raw, email_raw, password_raw, role_raw = (str(value or "").strip() for value in (row or (None, None, None, None)))

            if not any([username_raw, email_raw, password_raw, role_raw]):
                #ignore completely empty rows
                continue

            email_lower = email_raw.lower()
            role_lower = role_raw.lower()

            #only super admins can import admin accounts
            if role_lower == "admin" and not request.user.is_superuser:
                skipped_invalid.append({
                    "row": idx,
                    "reason": "Only Super Admins can import Admin accounts"})
                continue


            if not username_raw or not email_lower or not password_raw or role_lower not in role_groups:
                skipped_invalid.append({"row": idx, "reason": "Missing fields or invalid role"})
                continue

            #validate username format before importing the user
            try:
                User._meta.get_field("username").run_validators(username_raw)
            except ValidationError:
                skipped_invalid.append({
                    "row": idx,
                    "reason": "Invalid username"
                })
                continue

            #check whether the username already exists or not
            if User.objects.filter(username__iexact=username_raw).exists():
                skipped_invalid.append({
                    "row": idx,
                    "reason": "Username already in use"
                })
                continue


            #reject invalid email formats during excel import
            try:
                validate_email(email_lower)
            except ValidationError:
                skipped_invalid.append({
                    "row": idx,
                    "reason": "Invalid email address"
                })
                continue

            if email_lower in seen:
                skipped_invalid.append({"row": idx, "reason": "Duplicate email in file"})
                continue
            if User.objects.filter(email__iexact=email_lower).exists():
                skipped_existing.append({"row": idx, "email": email_lower})
                continue

            try:
                validate_password(password_raw)
            except ValidationError as e:
                skipped_invalid.append({"row": idx, "reason": f"Weak password: {'; '.join(e.messages)}"})
                continue

            user = User.objects.create_user(username=username_raw, email=email_lower, password=password_raw)
            user.groups.add(role_groups[role_lower])
            created.append(user.id)
            seen.add(email_lower)

    return JsonResponse({
        "createdCount": len(created),
        "skippedExisting": skipped_existing,
        "skippedInvalid": skipped_invalid,
    }, status=201)
