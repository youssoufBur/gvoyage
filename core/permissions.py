from rest_framework import permissions
from django.utils.translation import gettext_lazy as _


class IsAuthenticatedAndVerified(permissions.BasePermission):
    """
    Permission qui nécessite que l'utilisateur soit authentifié et vérifié.
    """
    message = _("Votre compte doit être vérifié pour effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_verified and
            request.user.is_active
        )


# =============================================================================
# PERMISSIONS PAR RÔLE
# =============================================================================

class IsAdmin(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est administrateur.
    """
    message = _("Seuls les administrateurs peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin())


class IsClient(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est client.
    """
    message = _("Seuls les clients peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_client())


class IsChauffeur(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est chauffeur.
    """
    message = _("Seuls les chauffeurs peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_chauffeur())


class IsCaissier(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est caissier.
    """
    message = _("Seuls les caissiers peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_caissier())


class IsLivreur(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est livreur.
    """
    message = _("Seuls les livreurs peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_livreur())


class IsAgent(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est agent d'agence.
    """
    message = _("Seuls les agents d'agence peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_agent())


class IsStaff(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est staff (chauffeur, caissier, agent, livreur ou admin).
    """
    message = _("Seuls les membres du staff peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsEmployee(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est employé (non-client).
    """
    message = _("Seuls les employés peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_employee())


class IsManager(permissions.BasePermission):
    """
    Permission personnalisée pour vérifier si l'utilisateur est manager (chef d'agence, central, national, DG).
    """
    message = _("Seuls les managers peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_manager())


# =============================================================================
# PERMISSIONS MÉTIER SPÉCIFIQUES
# =============================================================================

class CanScanTickets(permissions.BasePermission):
    """
    Permission pour scanner les tickets (caissiers, agents et staff d'agence).
    """
    message = _("Vous n'avez pas la permission de scanner les tickets.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return (request.user.is_caissier() or 
                request.user.is_agent() or 
                (request.user.is_staff and request.user.agency is not None))


class CanManageParcels(permissions.BasePermission):
    """
    Permission pour gérer les colis (staff d'agence et livreurs).
    """
    message = _("Vous n'avez pas la permission de gérer les colis.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return (request.user.is_staff and request.user.agency is not None) or request.user.is_livreur()
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_livreur():
            # Les livreurs peuvent gérer les colis qui leur sont assignés
            if hasattr(obj, 'last_handled_by'):
                return obj.last_handled_by == request.user
            if hasattr(obj, 'delivery_person'):
                return obj.delivery_person == request.user
        
        if request.user.is_staff and request.user.agency:
            # Le staff peut gérer les colis de son agence
            if hasattr(obj, 'current_agency'):
                return obj.current_agency == request.user.agency
            elif hasattr(obj, 'origin_agency'):
                return obj.origin_agency == request.user.agency
            elif hasattr(obj, 'destination_agency'):
                return obj.destination_agency == request.user.agency
        
        return False


class CanViewFinancialData(permissions.BasePermission):
    """
    Permission pour visualiser les données financières (managers et admin).
    """
    message = _("Vous n'avez pas la permission de visualiser les données financières.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_manager() or request.user.is_admin() or request.user.is_dg()


class CanManageUsers(permissions.BasePermission):
    """
    Permission pour gérer les utilisateurs (admin et managers).
    """
    message = _("Vous n'avez pas la permission de gérer les utilisateurs.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_manager() or request.user.is_admin()
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_manager():
            # Les managers peuvent gérer les utilisateurs de leurs agences
            if hasattr(obj, 'agency'):
                return request.user.can_manage_agency(obj.agency)
        
        return False


# =============================================================================
# PERMISSIONS HIÉRARCHIQUES ET ACCÈS AGENCE
# =============================================================================

class IsAgencyStaff(permissions.BasePermission):
    """
    Permission qui permet au staff d'une agence d'accéder aux données de leur agence.
    """
    message = _("Vous n'avez pas accès aux données de cette agence.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_admin():
            return True
        
        return request.user.is_staff and request.user.agency is not None
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        user_agency = request.user.agency
        
        # Vérifier l'agence selon le type d'objet
        if hasattr(obj, 'agency'):
            return obj.agency == user_agency
        elif hasattr(obj, 'vehicle'):
            return obj.vehicle.agency == user_agency
        elif hasattr(obj, 'trip'):
            return obj.trip.agency == user_agency
        elif hasattr(obj, 'schedule'):
            return obj.schedule.agency == user_agency
        elif hasattr(obj, 'route'):
            return obj.route.agency == user_agency
        elif hasattr(obj, 'origin_agency'):
            return obj.origin_agency == user_agency
        elif hasattr(obj, 'destination_agency'):
            return obj.destination_agency == user_agency
        elif hasattr(obj, 'current_agency'):
            return obj.current_agency == user_agency
        
        return False


class IsAgencyManager(permissions.BasePermission):
    """
    Permission qui permet aux managers d'agence d'accéder aux données de leurs agences gérées.
    """
    message = _("Vous n'avez pas accès aux données de ces agences.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_admin() or request.user.is_dg():
            return True
        
        return request.user.is_manager()
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin() or request.user.is_dg():
            return True
        
        if not request.user.is_manager():
            return False
        
        # Vérifier si l'utilisateur peut gérer l'agence de l'objet
        if hasattr(obj, 'agency'):
            return request.user.can_manage_agency(obj.agency)
        elif hasattr(obj, 'vehicle'):
            return request.user.can_manage_agency(obj.vehicle.agency)
        elif hasattr(obj, 'trip'):
            return request.user.can_manage_agency(obj.trip.agency)
        
        return False


class IsDriverOrAgencyStaff(permissions.BasePermission):
    """
    Permission spécifique pour les actions des chauffeurs et du staff d'agence.
    """
    message = _("Seuls les chauffeurs ou le staff d'agence peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_chauffeur() or (request.user.is_staff and request.user.agency is not None)
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_chauffeur():
            # Vérifier si le chauffeur est associé à l'objet
            if hasattr(obj, 'driver'):
                return obj.driver == request.user
            elif hasattr(obj, 'trip') and hasattr(obj.trip, 'driver'):
                return obj.trip.driver == request.user
        
        if request.user.is_staff and request.user.agency:
            # Vérifier si l'objet appartient à l'agence du staff
            if hasattr(obj, 'agency'):
                return obj.agency == request.user.agency
            elif hasattr(obj, 'trip') and hasattr(obj.trip, 'agency'):
                return obj.trip.agency == request.user.agency
        
        return False


class IsCashierOrAgencyStaff(permissions.BasePermission):
    """
    Permission spécifique pour les actions des caissiers et du staff d'agence.
    """
    message = _("Seuls les caissiers ou le staff d'agence peuvent effectuer cette action.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_caissier() or (request.user.is_staff and request.user.agency is not None)
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_caissier():
            # Les caissiers peuvent gérer les paiements de leur agence
            if hasattr(obj, 'agency'):
                return obj.agency == request.user.agency
            elif hasattr(obj, 'reservation') and hasattr(obj.reservation, 'schedule'):
                return obj.reservation.schedule.agency == request.user.agency
        
        if request.user.is_staff and request.user.agency:
            # Vérifier si l'objet appartient à l'agence du staff
            if hasattr(obj, 'agency'):
                return obj.agency == request.user.agency
        
        return False


# =============================================================================
# PERMISSIONS DE PROPRIÉTÉ ET ACCÈS PERSONNEL
# =============================================================================

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission qui permet aux utilisateurs de modifier leur propre profil,
    ou aux administrateurs de modifier tous les profils.
    """
    message = _("Vous n'avez pas la permission d'accéder à cette ressource.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        # Gestion des différents types d'objets
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'id'):
            return obj.id == request.user.id
        
        return obj == request.user


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Permission qui permet aux propriétaires ou au staff de voir/modifier l'objet.
    """
    message = _("Vous n'avez pas la permission d'accéder à cette ressource.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        
        # Vérifier si l'utilisateur est le propriétaire selon le type d'objet
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'client'):
            return obj.client == request.user
        elif hasattr(obj, 'sender'):
            return obj.sender == request.user
        elif hasattr(obj, 'buyer'):
            return obj.buyer == request.user
        elif hasattr(obj, 'passenger'):
            return obj.passenger == request.user
        elif hasattr(obj, 'driver'):
            return obj.driver == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsOwnerOrAgencyStaff(permissions.BasePermission):
    """
    Permission qui permet aux propriétaires ou au staff de l'agence concernée.
    """
    message = _("Vous n'avez pas la permission d'accéder à cette ressource.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        # Admin a tous les accès
        if request.user.is_admin():
            return True
        
        # Vérifier si l'utilisateur est le propriétaire
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        if hasattr(obj, 'client') and obj.client == request.user:
            return True
        if hasattr(obj, 'sender') and obj.sender == request.user:
            return True
        if hasattr(obj, 'buyer') and obj.buyer == request.user:
            return True
        
        # Vérifier si le staff a accès via son agence
        if request.user.is_staff and request.user.agency:
            if hasattr(obj, 'agency') and obj.agency == request.user.agency:
                return True
            if hasattr(obj, 'origin_agency') and obj.origin_agency == request.user.agency:
                return True
            if hasattr(obj, 'destination_agency') and obj.destination_agency == request.user.agency:
                return True
            if hasattr(obj, 'current_agency') and obj.current_agency == request.user.agency:
                return True
        
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission qui permet aux propriétaires de modifier, lecture seule pour les autres.
    """
    message = _("Vous n'avez pas la permission de modifier cette ressource.")
    
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Vérifier la propriété
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'client'):
            return obj.client == request.user
        elif hasattr(obj, 'sender'):
            return obj.sender == request.user
        elif hasattr(obj, 'buyer'):
            return obj.buyer == request.user
        
        return False


class IsAdminOrCanManageUser(permissions.BasePermission):
    """
    Permission qui permet aux admins de tout faire, et aux managers de gérer les utilisateurs de leurs agences.
    """
    message = _("Vous n'avez pas la permission de gérer cet utilisateur.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Les admins ont tous les accès
        if request.user.is_admin():
            return True
        
        # Les managers peuvent gérer les utilisateurs
        if request.user.is_manager():
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        
        if request.user.is_manager():
            # Les managers peuvent gérer les utilisateurs de leurs agences
            if hasattr(obj, 'agency'):
                return request.user.can_manage_agency(obj.agency)
        
        # Les utilisateurs peuvent gérer leur propre profil
        return obj == request.user


# =============================================================================
# PERMISSIONS DE BASE REST FRAMEWORK ÉTENDUES
# =============================================================================

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission qui permet la lecture à tous mais l'écriture aux admins seulement.
    """
    message = _("Seuls les administrateurs peuvent modifier cette ressource.")
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_admin())


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Permission qui permet la lecture à tous mais l'écriture au staff seulement.
    """
    message = _("Seuls les membres du staff peuvent modifier cette ressource.")
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


# =============================================================================
# PERMISSION GÉNÉRIQUE CONFIGURABLE
# =============================================================================

class HasRolePermission(permissions.BasePermission):
    """
    Permission générique basée sur les rôles avec configuration flexible.
    """
    
    def __init__(self, allowed_roles=None, allowed_methods=None):
        self.allowed_roles = allowed_roles or []
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        self.message = _("Vous n'avez pas le rôle nécessaire pour effectuer cette action.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Vérifier la méthode HTTP
        if request.method not in self.allowed_methods:
            return False
        
        # Vérifier les rôles
        user_role = request.user.role
        return user_role in self.allowed_roles
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


# =============================================================================
# PERMISSIONS PRÉ-CONFIGURÉES POUR USAGE COURANT
# =============================================================================

class IsAdminOrAgencyManager(HasRolePermission):
    """Permission pour admin et managers d'agence"""
    def __init__(self, allowed_methods=None):
        super().__init__(
            allowed_roles=['admin', 'agency_manager', 'central_manager', 'national_manager', 'dg'],
            allowed_methods=allowed_methods
        )


class IsStaffOrManager(HasRolePermission):
    """Permission pour staff et managers"""
    def __init__(self, allowed_methods=None):
        super().__init__(
            allowed_roles=['admin', 'agency_manager', 'central_manager', 'national_manager', 'dg', 
                          'chauffeur', 'caissier', 'livreur', 'agent'],
            allowed_methods=allowed_methods
        )


class CanManageOperations(HasRolePermission):
    """Permission pour gérer les opérations (managers et staff opérationnel)"""
    def __init__(self, allowed_methods=None):
        super().__init__(
            allowed_roles=['admin', 'agency_manager', 'central_manager', 'national_manager', 'dg',
                          'chauffeur', 'caissier', 'agent'],
            allowed_methods=allowed_methods
        )


# =============================================================================
# PERMISSIONS SPÉCIALISÉES POUR FONCTIONNALITÉS AVANCÉES
# =============================================================================

class CanCreatePublication(permissions.BasePermission):
    """
    Permission pour créer des publications (managers et admin).
    """
    message = _("Seuls les managers peuvent créer des publications.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_manager() or request.user.is_admin()


class CanManageSystemConfig(permissions.BasePermission):
    """
    Permission pour gérer la configuration système (admin uniquement).
    """
    message = _("Seuls les administrateurs peuvent modifier la configuration système.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_admin()


class CanViewAuditLogs(permissions.BasePermission):
    """
    Permission pour visualiser les logs d'audit (admin et DG).
    """
    message = _("Seuls les administrateurs et le DG peuvent visualiser les logs d'audit.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_admin() or request.user.is_dg()


class CanExportData(permissions.BasePermission):
    """
    Permission pour exporter des données (managers et admin).
    """
    message = _("Seuls les managers peuvent exporter des données.")
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return request.user.is_manager() or request.user.is_admin()