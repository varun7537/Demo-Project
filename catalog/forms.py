from django import forms
from .models import Review, SupportTicket
from .models import Post, Reply

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content']

class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ['content']
        
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['comment']

class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description'] 