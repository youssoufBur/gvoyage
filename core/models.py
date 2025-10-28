from django.db import models

# Create your models here.
import uuid
import qrcode
import io
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(is_deleted=True, deleted=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def only_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)


class ActiveManager(models.Manager):
    """Manager pour filtrer uniquement les objets actifs (is_active=True)."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class TimeStampedModel(models.Model):
    """Base : UUID + horodatage + suppression logique."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager().all_with_deleted()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, soft=True):
        if soft:
            self.is_deleted = True
            self.deleted = timezone.now()
            self.save(update_fields=["is_deleted", "deleted"])
        else:
            super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted = None
        self.save(update_fields=["is_deleted", "deleted"])

    def hard_delete(self):
        super().delete()


class QRCodeMixin(models.Model):
    """Mixin pour générer des QR codes"""
    qr_token = models.CharField(max_length=64, unique=True, blank=True, verbose_name="QR Token")
    qr_image = models.ImageField(upload_to="qrcodes/", blank=True, null=True, verbose_name="QR Code")

    class Meta:
        abstract = True

    def generate_qr_code(self, data=None):
        """Génère un QR code pour l'objet"""
        if not data:
            data = self.qr_token
            
        if not data:
            return
            
        qr_img = qrcode.make(data)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        filename = f"{self.__class__.__name__.lower()}_{self.id}.png"
        
        self.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)