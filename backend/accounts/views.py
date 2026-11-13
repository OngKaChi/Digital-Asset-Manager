import json
from io import BytesIO

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.cache import cache
from django.core.exceptions import ValidationError
#from django.db import transaction
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook, load_workbook

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes
VALID_ROLES = {"admin", "editor", "viewer"}


def _rate_limit_key(request, email):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"login_attempts:{ip}:{email}"


def _user_payload(user):
    primary_group = user.groups.first()
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email,
        "role": primary_group.name if primary_group else None,
    }


def _is_admin(user):
    return user.is_authenticated and user.groups.filter(name="admin").exists()


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
        return generic_error

    # Success — clear the counter
    cache.delete(key)

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    if remember_me:
        request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
    else:
        request.session.set_expiry(0)  # Browser session

    return JsonResponse({"user": _user_payload(user)})


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
    logout(request)
    return JsonResponse({"success": True})


# Retrieve Current User information Function
@require_GET
def current_user_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated."}, status=401)

    return JsonResponse({"user": _user_payload(request.user)})


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

    if user.groups.filter(name="admin").exists():
        return JsonResponse({"detail": "Administrator accounts cannot be edited."}, status=403)
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

    if user.groups.filter(name="admin").exists():
        return JsonResponse({"detail": "Administrator accounts cannot be deleted."}, status=403)

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
