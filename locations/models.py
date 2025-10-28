from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class Country(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=3, unique=True, help_text="Code ISO-3166 alpha-2/3")

    class Meta:
        verbose_name = _("Pays")
        verbose_name_plural = _("Pays")

    def __str__(self):
        return f"{self.name} ({self.code})"


class City(TimeStampedModel):
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="cities")
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("country", "name")
        indexes = [models.Index(fields=["country", "name"])]
        verbose_name = _("Ville")
        verbose_name_plural = _("Villes")

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Agency(TimeStampedModel):
    class Level(models.TextChoices):
        NATIONAL = "national", "Siège national"
        CENTRAL = "central", "Agence centrale (ville)"
        LOCAL = "local", "Agence de quartier"

    class Type(models.TextChoices):
        DEPARTURE = "departure", "Agence de départ"
        ARRIVAL = "arrival", "Agence d'arrivée"
        CARGO = "cargo", "Agence de colis"
        SALES = "sales", "Point de vente / Caisse"
        SERVICE = "service", "Service administratif"
        OTHER = "other", "Autre"

    name = models.CharField(max_length=120, verbose_name=_("Nom de l'agence"))
    code = models.CharField(max_length=10, unique=True, verbose_name=_("Code agence"))
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="agencies")

    level = models.CharField(max_length=20, choices=Level.choices, default=Level.LOCAL)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SALES)

    parent_agency = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_agencies"
    )

    address = models.TextField(verbose_name=_("Adresse complète"))
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, verbose_name=_("Agence active"))

    class Meta:
        verbose_name = _("Agence")
        verbose_name_plural = _("Agences")
        indexes = [
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['level']),
            models.Index(fields=['type']),
        ]
        ordering = ["city__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_level_display()} - {self.get_type_display()})"