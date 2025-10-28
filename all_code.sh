#!/bin/bash

# Script pour extraire les fichiers models, urls, views et serializers de toutes les applications Django
# Usage: ./extract_django_code.sh

# Couleurs pour le output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Extraction du code Django ===${NC}"

# Liste des applications Django
APPS=("users" "locations" "transport" "reservations" "parcel" "publications" "parameter" "core")

# Fonction pour extraire un type de fichier
extract_files() {
    local file_type=$1
    local output_file=$2
    local file_extension=$3
    
    echo -e "${YELLOW}Extraction des fichiers $file_type...${NC}"
    
    # Vider le fichier de sortie ou le créer
    > "$output_file"
    
    # En-tête du fichier
    echo -e "# ==================================================" >> "$output_file"
    echo -e "# FICHIER: $output_file" >> "$output_file"
    echo -e "# DESCRIPTION: Tous les fichiers $file_type des applications Django" >> "$output_file"
    echo -e "# GÉNÉRÉ LE: $(date)" >> "$output_file"
    echo -e "# ==================================================\n" >> "$output_file"
    
    local file_count=0
    
    for app in "${APPS[@]}"; do
        local file_path="./$app/$file_type$file_extension"
        
        if [[ -f "$file_path" ]]; then
            echo -e "${GREEN}✓${NC} Ajout de $file_path"
            
            # En-tête de l'application
            echo -e "\n# ==================================================" >> "$output_file"
            echo -e "# APPLICATION: $app" >> "$output_file"
            echo -e "# FICHIER: $file_type$file_extension" >> "$output_file"
            echo -e "# ==================================================\n" >> "$output_file"
            
            # Contenu du fichier
            cat "$file_path" >> "$output_file"
            
            # Séparateur entre les applications
            echo -e "\n\n" >> "$output_file"
            
            ((file_count++))
        else
            echo -e "${RED}✗${NC} Fichier non trouvé: $file_path"
        fi
    done
    
    echo -e "${GREEN}✅ Extraction $file_type terminée: $file_count fichiers → $output_file${NC}"
}

# Extraction des models
extract_files "models" "all_models.py" ".py"

# Extraction des urls
extract_files "urls" "all_urls.py" ".py"

# Extraction des views
extract_files "views" "all_views.py" ".py"

# Extraction des serializers (si ils existent)
extract_files "serializers" "all_serializers.py" ".py"

# Extraction des admin (bonus)
extract_files "admin" "all_admin.py" ".py"

echo -e "${BLUE}=== Résumé ===${NC}"
echo -e "Fichiers générés:"
echo -e "  - ${GREEN}all_models.py${NC}      (Tous les modèles)"
echo -e "  - ${GREEN}all_urls.py${NC}        (Toutes les URLs)"
echo -e "  - ${GREEN}all_views.py${NC}       (Toutes les vues)" 
echo -e "  - ${GREEN}all_serializers.py${NC} (Tous les serializers)"
echo -e "  - ${GREEN}all_admin.py${NC}       (Toutes les configurations admin)"

# Vérification de la taille des fichiers
echo -e "\n${BLUE}=== Taille des fichiers générés ===${NC}"
for file in all_models.py all_urls.py all_views.py all_serializers.py all_admin.py; do
    if [[ -f "$file" ]]; then
        lines=$(wc -l < "$file")
        echo -e "  - $file: ${YELLOW}$lines lignes${NC}"
    fi
done

echo -e "\n${GREEN}✅ Extraction terminée avec succès!${NC}"