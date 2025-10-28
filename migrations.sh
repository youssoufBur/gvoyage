#!/bin/bash

# Script: reset_migrations.sh
# Description: Supprime complètement les dossiers migrations et refait les migrations
# Auteur: G-Travel
# Usage: ./reset_migrations.sh ou bash reset_migrations.sh

set -e  # Arrête le script en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérifier si nous sommes dans un environnement virtuel Python
check_environment() {
    if [ -z "$VIRTUAL_ENV" ]; then
        print_warning "Aucun environnement virtuel détecté."
        read -p "Voulez-vous continuer ? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Liste des applications Django
APPS=("core" "users" "locations" "parameter" "transport" "reservations" "parcel" "publications")

# Fichiers de base de données possibles
DB_FILES=("db.sqlite3" "dev.db" "test.db" "database.sqlite3")

# Fonction pour supprimer complètement les dossiers migrations
delete_migrations_folders() {
    print_info "Suppression complète des dossiers migrations..."
    
    for app in "${APPS[@]}"; do
        if [ -d "$app/migrations" ]; then
            print_info "Suppression du dossier migrations pour: $app"
            rm -rf "$app/migrations"
            print_success "Dossier migrations supprimé pour: $app"
        else
            print_warning "Dossier migrations non trouvé pour: $app"
        fi
    done
}

# Fonction pour recréer les dossiers migrations avec __init__.py
recreate_migrations_folders() {
    print_info "Recréation des dossiers migrations..."
    
    for app in "${APPS[@]}"; do
        print_info "Création du dossier migrations pour: $app"
        mkdir -p "$app/migrations"
        touch "$app/migrations/__init__.py"
        print_success "Dossier migrations recréé pour: $app"
    done
}

# Fonction pour supprimer la base de données
delete_database() {
    print_info "Recherche des fichiers de base de données..."
    
    db_found=false
    for db_file in "${DB_FILES[@]}"; do
        if [ -f "$db_file" ]; then
            db_found=true
            print_warning "Base de données détectée: $db_file"
        fi
    done
    
    if [ "$db_found" = true ]; then
        read -p "Voulez-vous supprimer tous les fichiers de base de données ? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for db_file in "${DB_FILES[@]}"; do
                if [ -f "$db_file" ]; then
                    rm -f "$db_file"
                    print_success "Base de données supprimée: $db_file"
                fi
            done
        else
            print_info "Conservation des bases de données existantes"
        fi
    else
        print_info "Aucun fichier de base de données trouvé"
    fi
}

# Fonction pour nettoyer les fichiers pycache
clean_pycache() {
    print_info "Nettoyage des fichiers __pycache__..."
    
    # Supprimer tous les dossiers __pycache__ dans le projet
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete
    find . -name "*.pyo" -delete
    find . -name ".coverage" -delete
    
    print_success "Nettoyage des fichiers cache terminé"
}

# Fonction pour créer les nouvelles migrations
create_migrations() {
    print_info "Création des nouvelles migrations..."
    
    # Créer les migrations pour chaque application
    for app in "${APPS[@]}"; do
        print_info "Création des migrations pour: $app"
        if python manage.py makemigrations "$app" 2>/dev/null; then
            print_success "Migrations créées pour: $app"
        else
            print_warning "Aucune migration nécessaire pour: $app"
        fi
    done
    
    # Faire aussi makemigrations sans app spécifique pour les migrations globales
    print_info "Création des migrations globales..."
    python manage.py makemigrations
}

# Fonction pour appliquer les migrations
apply_migrations() {
    print_info "Application des migrations..."
    python manage.py migrate
}

# Fonction pour vérifier l'état des migrations
check_migrations() {
    print_info "Vérification de l'état des migrations..."
    python manage.py showmigrations
}

# Fonction pour créer le superutilisateur (optionnel)
create_superuser() {
    print_info "Création d'un superutilisateur..."
    read -p "Voulez-vous créer un superutilisateur ? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python manage.py createsuperuser
    else
        print_info "Vous pourrez créer un superutilisateur plus tard avec: python manage.py createsuperuser"
    fi
}

# Fonction pour afficher un résumé
show_summary() {
    print_success "=== RÉSUMÉ DES ACTIONS EFFECTUÉES ==="
    echo "✓ Dossiers migrations supprimés et recréés"
    echo "✓ Fichiers cache nettoyés"
    echo "✓ Migrations recréées"
    echo "✓ Migrations appliquées"
    echo ""
    print_info "Prochaines étapes:"
    echo "1. Démarrer le serveur: python manage.py runserver"
    echo "2. Créer un superutilisateur si nécessaire: python manage.py createsuperuser"
    echo "3. Vérifier que tout fonctionne correctement"
}

# Fonction principale
main() {
    print_info "Début du processus de réinitialisation complète des migrations"
    echo "=========================================================="
    
    # Vérifier que manage.py existe
    if [ ! -f "manage.py" ]; then
        print_error "Fichier manage.py non trouvé. Exécutez ce script depuis la racine du projet Django."
        exit 1
    fi
    
    # Vérifier l'environnement
    check_environment
    
    # Afficher les applications qui seront traitées
    print_info "Applications qui seront traitées:"
    for app in "${APPS[@]}"; do
        echo "  - $app"
    done
    echo
    
    # Demander confirmation
    print_warning "ATTENTION: Cette action va:"
    echo "  - Supprimer COMPLÈTEMENT tous les dossiers migrations"
    echo "  - Supprimer potentiellement la base de données"
    echo "  - Recréer toutes les migrations depuis zéro"
    echo ""
    read -p "Êtes-vous sûr de vouloir continuer ? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Opération annulée"
        exit 0
    fi
    
    # Exécution des étapes
    delete_migrations_folders
    echo
    
    delete_database
    echo
    
    clean_pycache
    echo
    
    recreate_migrations_folders
    echo
    
    create_migrations
    echo
    
    apply_migrations
    echo
    
    check_migrations
    echo
    
    create_superuser
    echo
    
    show_summary
}

# Exécuter la fonction principale
main "$@"