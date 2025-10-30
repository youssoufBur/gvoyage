# users/backends.py
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()

class PhoneBackend(ModelBackend):
    """
    Authentifie via le numéro de téléphone
    """
    def authenticate(self, request, phone=None, password=None, **kwargs):
        if phone is None or password is None:
            return None
        
        try:
            # Chercher l'utilisateur par téléphone
            user = User.objects.get(
                Q(phone=phone) | 
                Q(phone__icontains=phone)
            )
            
            # Vérifier le mot de passe
            if user.check_password(password):
                return user
            return None
                
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            return None