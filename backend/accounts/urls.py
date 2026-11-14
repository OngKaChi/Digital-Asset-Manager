from django.urls import path

from . import views


app_name = "accounts"


urlpatterns = [
	path("login/", views.login_view, name="login"),
    path("forgot-password/", views.forgot_password_view, name="forgot-password"),
	path("reset-password/", views.reset_password_view, name="reset-password"),
	path("logout/", views.logout_view, name="logout"),
	path("me/", views.current_user_view, name="current-user"),
    path("user-audit-log/", views.user_audit_log_view, name="user-audit-log"),
    path("users/", views.user_list_view, name="user-list"),
    path("users/sample/", views.user_import_sample_view, name="user-import-sample"),
    path("create-user/", views.create_user_view, name="create-user"),
    path("update-user/<int:user_id>/", views.update_user_view, name="update-user"),
    path("delete-user/<int:user_id>/", views.delete_user_view, name="delete-user"),
    path("users/bulk-import/", views.bulk_import_users_view, name="bulk_import_users"),
]
