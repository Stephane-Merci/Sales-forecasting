from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer
)
from .utils import send_verification_email, send_password_reset_email
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse

User = get_user_model()

def home_view(request):
    # Home view can be accessed by anyone, but content will be conditional
    return render(request, 'home.html')

@login_required
def profile_view(request):
    if request.method == 'POST':
        user = request.user
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.phone_number = request.POST.get('phone_number')
        
        try:
            user.full_clean()
            user.save()
            messages.success(request, 'Profile updated successfully!')
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    return render(request, 'authentication/profile.html')

@login_required
def change_password_view(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('profile')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('profile')
        
        try:
            validate_password(new_password, request.user)
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('login')
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
    
    return redirect('profile')

@login_required
def verify_email_view(request):
    return render(request, 'authentication/verify_email.html')

@login_required
def resend_verification_view(request):
    if not request.user.is_verified:
        # Check if user has an email before attempting to send
        if request.user.email:
            print(f"Attempting to send verification email to: {request.user.email}") # Debug print
            try:
                send_verification_email(request.user) # Assuming send_verification_email handles the domain/site URL correctly
                messages.success(request, 'Verification email has been sent.')
            except Exception as e:
                messages.error(request, f'Error sending verification email: {e}')
                # Consider logging the error for debugging
        else:
            messages.error(request, 'Your account does not have an email address to send verification to.')
    else:
        messages.info(request, 'Your email is already verified.')
        
    # Always redirect after attempting to resend
    return redirect('verify_email')

# Template-based views
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home') # Redirect authenticated users away from login
        
    if request.method == 'POST':
        email = request.POST.get('email') # Get email from the form data
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Successfully logged in!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
            # Optionally, render the login template again with preserved email
            return render(request, 'authentication/login.html', {'email': email})
    
    return render(request, 'authentication/login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home') # Redirect authenticated users away from register
        
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        phone = request.POST.get('phone')

        # Validate required fields (basic check before serializer)
        if not all([username, email, password1, password2]):
            messages.error(request, "All fields are required.")
            return render(request, 'authentication/register.html', {
                'username': username,
                'email': email,
                'phone': phone
            })

        # Check if passwords match
        if password1 != password2:
            messages.error(request, "Passwords don't match.")
            return render(request, 'authentication/register.html', {
                'username': username,
                'email': email,
                'phone': phone
            })

        # Prepare data for serializer
        data = {
            'username': username,
            'email': email,
            'password': password1,
            'password2': password2, # Include password2 for the serializer
            'phone_number': phone
        }

        # Create user
        serializer = UserRegistrationSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Please verify your email.')
            return redirect('verify_email')
        else:
            # Serializer validation failed (e.g., password strength, email format) and password matching
            for field, errors in serializer.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            # Render the form again with previous data
            return render(request, 'authentication/register.html', {
                'username': username,
                'email': email,
                'phone': phone
            })
    
    return render(request, 'authentication/register.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Successfully logged out!')
    return redirect('login')

def password_reset_view(request):
    if request.user.is_authenticated:
        return redirect('home') # Redirect authenticated users away from password reset
        
    if request.method == 'POST':
        serializer = PasswordResetRequestSerializer(data=request.POST)
        if serializer.is_valid():
            try:
                user = User.objects.get(email=serializer.validated_data['email'])
                send_password_reset_email(user)
                messages.success(request, 'Password reset email has been sent.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'No user found with this email address.')
    
    return render(request, 'authentication/password_reset.html')

def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, "Passwords don't match.")
                return render(request, 'authentication/password_reset_confirm.html', {'uidb64': uidb64, 'token': token})

            try:
                validate_password(new_password, user)
                user.set_password(new_password)
                user.save()
                messages.success(request, 'Your password has been set. You can now log in.')
                return redirect('login')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
                return render(request, 'authentication/password_reset_confirm.html', {'uidb64': uidb64, 'token': token})

        else:
            # Render the confirmation form
            return render(request, 'authentication/password_reset_confirm.html', {'uidb64': uidb64, 'token': token})
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('password_reset') # Redirect to password reset request page if link is invalid

def email_verification_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_verified = True
        user.save()
        messages.success(request, 'Your email address has been verified. You can now log in.')
        return redirect('login') # Redirect to login after successful verification
    else:
        messages.error(request, 'The email verification link is invalid or has expired.')
        return redirect('home') # Redirect to home or a relevant page if link is invalid

# API views
class UserRegistrationView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email after successful registration
        print(f"Attempting to send verification email to: {user.email}") # Debug print
        try:
             send_verification_email(user) # Assuming send_verification_email handles the domain/site URL correctly
        except Exception as e:
             print(f"Error sending verification email during registration: {e}") # Debug print
             # Consider logging the error more formally

        
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': serializer.data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class UserLoginView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = UserLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

class PasswordResetRequestView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            user = User.objects.get(email=serializer.validated_data['email'])
            send_password_reset_email(user) # Assuming send_password_reset_email handles the domain/site URL correctly
            return Response(
                {'message': 'Password reset email has been sent.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User with this email does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )

class PasswordResetConfirmView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        user.set_password(serializer.validated_data['password'])
        user.save()
        
        return Response(
            {'message': 'Password has been reset successfully.'},
            status=status.HTTP_200_OK
        )

class EmailVerificationView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        user.is_verified = True
        user.save()
        
        return Response(
            {'message': 'Email has been verified successfully.'},
            status=status.HTTP_200_OK
        )
