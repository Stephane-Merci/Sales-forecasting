from django.urls import path, re_path
from .views import (
    UserRegistrationView,
    UserLoginView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    EmailVerificationView,
    login_view,
    register_view,
    logout_view,
    password_reset_view,
    home_view,
    profile_view,
    change_password_view,
    verify_email_view,
    resend_verification_view,
    password_reset_confirm_view,
    email_verification_confirm_view
)

urlpatterns = [
    # Home page
    path('', home_view, name='home'),
    
    # Template-based URLs
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('password-reset/', password_reset_view, name='password_reset'),
    re_path(r'^password-reset/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z_-]+)/$', 
            password_reset_confirm_view, name='password_reset_confirm'),
    path('profile/', profile_view, name='profile'),
    path('profile/change-password/', change_password_view, name='change_password'),
    path('verify-email/', verify_email_view, name='verify_email'),
    re_path(r'^verify-email/confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z_-]+)/$', 
            email_verification_confirm_view, name='email_verification_confirm'),
    path('resend-verification/', resend_verification_view, name='resend_verification'),
    
    # API URLs
    path('api/register/', UserRegistrationView.as_view(), name='api-register'),
    path('api/login/', UserLoginView.as_view(), name='api-login'),
    path('api/password-reset/', PasswordResetRequestView.as_view(), name='api-password-reset'),
    path('api/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='api-password-reset-confirm'),
    path('api/verify-email/', EmailVerificationView.as_view(), name='api-verify-email'),
] 