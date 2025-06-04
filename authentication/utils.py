from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.contrib.sites.models import Site

def send_verification_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Get the current site domain
    current_site = Site.objects.get_current()
    domain = current_site.domain
    
    # Generate the email verification confirmation URL
    # Use reverse to get the URL for the 'email_verification_confirm' view
    verification_path = reverse('email_verification_confirm', kwargs={'uidb64': uid, 'token': token})
    verification_url = f'http://{domain}{verification_path}'
    
    subject = 'Verify your email address'
    message = f'Please click the following link to verify your email: {verification_url}'
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

def send_password_reset_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    print(f"Debug: uidb64 = {uid}") # Debug print
    print(f"Debug: token = {token}") # Debug print

    current_site = Site.objects.get_current()
    domain = current_site.domain
    
    reset_path = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
    reset_url = f'http://{domain}{reset_path}'
    
    subject = 'Reset your password'
    message = f'Please click the following link to reset your password: {reset_url}'
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    ) 