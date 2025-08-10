from django.shortcuts import render, get_object_or_404, redirect
from .models import Course, Category, Lesson, Review, Enrollment, LessonProgress, SupportTicket, Post, Reply, Quiz
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.urls import reverse
from .forms import ReviewForm, SupportTicket
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .forms import SupportTicketForm, PostForm, ReplyForm
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from django.core.mail import send_mail
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.http import FileResponse, Http404
import os
from zoomus import ZoomClient
from django.conf import settings

def course_list(request):
    courses = Course.objects.all()
    return render(request, 'catalog/course_list.html', {'courses': courses})

def search(request):
    query = request.GET.get('q')
    results = Course.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query)
    ) if query else []
    return render(request, 'catalog/search_results.html', {'results': results, 'query': query})

@login_required

@login_required
def enroll_course(request, pk):
    course = get_object_or_404(Course, pk=pk)
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)

    if created:
        send_mail(
            subject=f"New Enrollment for {course.title}",
            message=f"{request.user.username} has enrolled in your course: {course.title}.",
            from_email=None,
            recipient_list=[course.instructor.email],
        )

    return redirect('course_detail', pk=pk)

@login_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(user=request.user)
    return render(request, 'catalog/my_courses.html', {'enrollments': enrollments})


def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    reviews = course.reviews.all()
    enrolled = False
    lessons_done = 0
    total_lessons = course.lessons.count()
    lesson_progress_map = {}
    form = ReviewForm() 

    if request.user.is_authenticated:
        enrolled = Enrollment.objects.filter(user=request.user, course=course).exists()
        lessons_done = LessonProgress.objects.filter(user=request.user, lesson__course=course, completed=True).count()
        announcements = course.announcements.order_by('-created_at')

        lessons_done = LessonProgress.objects.filter(
            user=request.user,
            lesson__course=course,
            completed=True
        ).count()

        lesson_progress_qs = LessonProgress.objects.filter(user=request.user, lesson__course=course)
        lesson_progress_map = {lp.lesson_id: lp for lp in lesson_progress_qs}

    progress = 0
    if total_lessons > 0:
        progress = int((lessons_done / total_lessons) * 100)

    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.course = course
                review.save()
                return redirect('course_detail', pk=pk)
        else:
            return redirect('login')

    return render(request, 'catalog/course_detail.html', {
        'course': course,
        'reviews': reviews,
        'enrolled': enrolled,
        'progress': progress,
        'form': form,
        'lesson_progress_map': lesson_progress_map,
        'announcements': announcements
    })


def categories_list(request):
    categories = Category.objects.all()
    return render(request, 'catalog/categories.html', {'categories': categories})

def category_courses(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    courses = Course.objects.filter(category=category)
    return render(request, 'catalog/category_courses.html', {'category': category, 'courses': courses})

@login_required
def profile(request):
    enrollments = Enrollment.objects.filter(user=request.user)
    reviews = Review.objects.filter(user=request.user)
    return render(request, 'catalog/profile.html', {
        'enrollments': enrollments,
        'reviews': reviews,
    })

@login_required
def mark_completed(request, pk):
    enrollment = get_object_or_404(Enrollment, user=request.user, course__pk=pk)
    enrollment.is_completed = True
    enrollment.save()
    return redirect('course_detail', pk=pk)

@login_required
def mark_lesson_complete(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    LessonProgress.objects.get_or_create(user=request.user, lesson=lesson, default={'completed': True})
    LessonProgress.objects.filter(user=request.user, lesson=lesson).update(completed=True)
    return redirect('course_detail', pk=lesson.course.pk)

def search(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')
    course = Course.objects.all()

    if query:
        course = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(instructor__icontains=query)
        )

    if category_id:
        course = course.filter(category_id=category_id)

    categories = Category.objects.all()

    return render(request, 'catalog/search_results.html',{
        'results': course,
        'query': query,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
    })

@login_required
def instructor_dashboard(request):
    my_courses = Course.objects.filter(instructor=request.user)
    course_data = []
    for course in my_courses:
        enrolled_students = Enrollment.objects.filter(course=course)
        course_data.append({
            'course': course,
            'enrollments': enrolled_students,
            'num_enrollments': enrolled_students.count()
        })
    return render(request, 'catalog/instructor_dashboard.html', {
        'course_data': course_data
    })

@login_required
def submit_ticket(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.user = request.user
            ticket.save()
            return redirect('ticket_thanks')
    else:
        form = SupportTicketForm()
    return render(request, 'catalog/submit_ticket.html', {'form': form})

def ticket_thanks(request):
    return render(request, 'catalog/ticket_thanks.html')

@login_required
def course_forum(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    posts = Post.objects.filter(course=course).order_by('-created_at')

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.user = request.user
            new_post.course = course
            new_post.save()

            send_mail(
                subject=f"New Forum Post in {course.title}",
                message=f"{request.user.username} posted a message in {course.title}'s discussion forum.",
                from_email=None,
                recipient_list=[course.instructor.email],
            )

            return redirect('course_forum', course_id=course_id)
    else:
        form = PostForm()

    return render(request, 'catalog/course_forum.html', {
        'course': course,
        'posts': posts,
        'form': form
    })

@login_required
def reply_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.method == 'POST':
        form = ReplyForm(request.POST)
        if form.is_valid():
            new_reply = form.save(commit=False)
            new_reply.user = request.user
            new_reply.post = post
            new_reply.save()
            return redirect('course_forum', course_id=post.course.pk)
    return redirect('course_forum', course_id=post.course.pk)

@login_required
def download_certificate(request, course_id):
    enrollment = get_object_or_404(Enrollment, user=request.user, course_id=course_id, is_completed=True)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 24)
    p.drawString(200, 700, "Certificate of Completion")
    p.setFont("Helvetica", 14)
    p.drawString(100, 650, f"This certifies that {request.user.get_full_name() or request.user.username}")
    p.drawString(100, 630, f"has successfully completed the course:")
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 610, f"{enrollment.course.title}")
    p.setFont("Helvetica", 12)
    p.drawString(100, 580, f"Date: {enrollment.enrolled_at.date()}")
    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total = questions.count()

        for question in questions:
            selected = int(request.POST.get(f"question_{question.id}"))
            if selected == question.correct_option:
                score += 1

        return render(request, 'catalog/quiz_result.html', {
            'quiz': quiz,
            'score': score,
            'total': total,
        })

    return render(request, 'catalog/take_quiz.html', {
        'quiz': quiz,
        'questions': questions,
    })

def bundle_list(request):
    bundles = Bundle.objects.all()
    return render(request, 'catalog/bundle_list.html', {'bundles': bundles})



stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def buy_bundle(request, bundle_id):
    bundle = get_object_or_404(Bundle, id=bundle_id)
    order = BundleOrder.objects.create(user=request.user, bundle=bundle)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': bundle.name,
                },
                'unit_amount': int(bundle.price * 100),
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=request.build_absolute_uri(f'/bundles/success/{order.id}/'),
        cancel_url=request.build_absolute_uri('/bundles/'),
    )

    return redirect(checkout_session.url)


@login_required
def bundle_success(request, order_id):
    order = get_object_or_404(BundleOrder, id=order_id, user=request.user)
    order.paid = True
    order.save()

    for course in order.bundle.courses.all():
        Enrollment.objects.get_or_create(user=request.user, course=course)

    return render(request, 'catalog/bundle_success.html', {'bundle': order.bundle})

@login_required
def stream_video(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    enrolled = Enrollment.objects.filter(user=request.user, course=lesson.course, is_completed=False).exists()

    if not enrolled:
        raise Http404("Not authorized")

    video_path = lesson.video.path
    return FileResponse(open(video_path, 'rb'), content_type='video/mp4')

def create_zoom_meeting(topic, start_time):
    client = ZoomClient(settings.ZOOM_API_KEY, settings.ZOOM_API_SECRET)
    response = client.meeting.create(
        user_id="me",
        topic=topic,
        type=2, 
        start_time=start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        duration=60
    )
    return response['join_url']

@login_required
def schedule_live_class(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        topic = request.POST['topic']
        start_time = request.POST['start_time']
        start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
        zoom_link = create_zoom_meeting(topic, start_dt)
        LiveClass.objects.create(course=course, topic=topic, start_time=start_dt, zoom_link=zoom_link)
        return redirect('course_detail', pk=course.id)
    return render(request, 'catalog/schedule_live_class.html', {'course': course})

@login_required
def complete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    profile = request.user.profile
    profile.points += 10  
    profile.update_badge()
    return redirect('lesson_detail', lesson_id=lesson.id)

def ajax_search(request):
    query = request.GET.get('q', '')
    results = []
    if query:
        courses = Course.objects.filter(title__icontains=query)[:5]
        results = [{'id': c.id, 'title': c.title} for c in courses]
    return JsonResponse({'results': results})

@login_required
def toggle_bookmark(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    bookmark, created = LessonBookmark.objects.get_or_create(user=request.user, lesson=lesson)
    if not created:
        bookmark.delete()
    return redirect('lesson_detail', lesson_id=lesson_id)