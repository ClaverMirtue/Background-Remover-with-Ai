import sys
import logging
import mimetypes

sys.setrecursionlimit(10000)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import UserRegistrationForm, ContactForm, ImageUploadForm
from .models import ProcessedImage, Contact
from rembg import remove
from PIL import Image
import io
import os
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import tempfile
import time

def is_admin(user):
    return user.is_superuser

def home(request):
    return render(request, 'removerapp/home.html')

def about(request):
    return render(request, 'removerapp/about.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
        messages.error(request, 'Registration failed. Please check your input.')
    else:
        form = UserRegistrationForm()
    return render(request, 'removerapp/register.html', {'form': form})

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message has been sent!')
            return redirect('home')
    else:
        form = ContactForm()
    return render(request, 'removerapp/contact.html', {'form': form})

@csrf_exempt
def remove_background(request):
    if request.method == 'POST':
        try:
            image_file = request.FILES.get('image')
            if not image_file:
                return JsonResponse({'success': False, 'error': 'No image file provided'})

            # Validate file size
            if image_file.size > 5242880:  # 5MB
                return JsonResponse({'success': False, 'error': 'File size too large. Maximum size is 5MB'})

            # Get file extension
            file_extension = os.path.splitext(image_file.name)[1].lower()
            
            # Validate file type using extension
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            if file_extension not in allowed_extensions:
                return JsonResponse({
                    'success': False, 
                    'error': f'Invalid file type. Allowed types are: {", ".join(allowed_extensions)}'
                })

            # Additional validation using PIL
            try:
                img = Image.open(image_file)
                if img.format.lower() not in ['jpeg', 'jpg', 'png']:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid image format. Please upload JPEG or PNG images'
                    })
                image_file.seek(0)  # Reset file pointer after reading
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid image file. Please upload a valid JPEG or PNG image'
                })

            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            temp_input_path = os.path.join(temp_dir, f'input_{int(time.time())}_{image_file.name}')

            try:
                # Save uploaded file
                with open(temp_input_path, 'wb+') as destination:
                    for chunk in image_file.chunks():
                        destination.write(chunk)

                # Process image
                with Image.open(temp_input_path) as img:
                    # Convert RGBA to RGB if necessary
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        bg.paste(img, mask=img.split()[-1])
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Resize large images
                    max_size = 2000
                    if img.width > max_size or img.height > max_size:
                        ratio = min(max_size/img.width, max_size/img.height)
                        new_size = (int(img.width * ratio), int(img.height * ratio))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Save processed image
                    img.save(temp_input_path, 'PNG')

                # Remove background
                with open(temp_input_path, 'rb') as input_file:
                    input_data = input_file.read()
                    output_data = remove(input_data)

                # Save result
                output_path = os.path.join(settings.MEDIA_ROOT, 'processed_images', f'processed_{image_file.name}')
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                with open(output_path, 'wb') as output_file:
                    output_file.write(output_data)

                # Clean up
                if os.path.exists(temp_input_path):
                    os.remove(temp_input_path)

                return JsonResponse({
                    'success': True,
                    'processed_image_url': f'{settings.MEDIA_URL}processed_images/processed_{image_file.name}'
                })

            except Exception as e:
                logger.error(f"Error processing image: {str(e)}")
                if os.path.exists(temp_input_path):
                    os.remove(temp_input_path)
                return JsonResponse({
                    'success': False,
                    'error': 'Error processing image. Please try again with a different image.'
                })

        except Exception as e:
            logger.error(f"Error in remove_background: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.'
            })

    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
@login_required
def upload_image(request):
    if request.method == 'POST':
        if 'image' in request.FILES:
            form = ImageUploadForm(request.POST, request.FILES)
            if form.is_valid():
                # Handle the image upload similar to remove_background view
                return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
def download_image(request, image_id):
    try:
        processed_image = ProcessedImage.objects.get(id=image_id, user=request.user)
        image_path = processed_image.processed_image.path
        with open(image_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='image/png')
            response['Content-Disposition'] = f'attachment; filename=processed_image.png'
            return response
    except ProcessedImage.DoesNotExist:
        messages.error(request, 'Image not found.')
        return redirect('home')

@user_passes_test(is_admin)
def admin_dashboard(request):
    processed_images = ProcessedImage.objects.all().order_by('-created_at')
    contacts = Contact.objects.all().order_by('-created_at')
    return render(request, 'removerapp/admin_dashboard.html', {
        'processed_images': processed_images,
        'contacts': contacts
    })
