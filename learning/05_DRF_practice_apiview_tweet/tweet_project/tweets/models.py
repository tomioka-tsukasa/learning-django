from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

# Create your models here.

class Tweet(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tweets",
        verbose_name="投稿者"
    )
    content = models.TextField(
        max_length=280,
        verbose_name="投稿内容"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="作成日時"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ツイート"
        verbose_name_plural = "ツイート"
    
    def __str__(self):
        return f"{self.autor.username}: {self.content[:20]}"
