from django.contrib import admin
from .models import Category, Course, Enrollment, Review, Lesson, LessonProgress, SupportTicket
from .models import Bundle
from .models import Announcement

admin.site.register(Announcement)
admin.site.register(Bundle)
admin.site.register(Category)
admin.site.register(Course)
admin.site.register(Lesson)
admin.site.register(SupportTicket)