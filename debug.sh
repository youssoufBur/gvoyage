#!/bin/bash

# Tester si /api/schema/ fonctionne

echo "=== TEST DU SCHÉMA API ==="

# Démarrer le serveur en arrière-plan
echo "Démarrage du serveur de test..."
python manage.py runserver 127.0.0.1:8001 &
SERVER_PID=$!

# Attendre que le serveur démarre
sleep 3

# Tester l'endpoint /api/schema/
echo "Test de /api/schema/..."
if curl -s http://127.0.0.1:8001/api/schema/ > /dev/null; then
    echo "✅ /api/schema/ fonctionne correctement"
else
    echo "❌ /api/schema/ retourne une erreur"
fi

# Arrêter le serveur
kill $SERVER_PID 2>/dev/null

# Test alternatif avec manage.py
echo "Test avec manage.py..."
if python manage.py spectacular --format openapi-json --validate 2>/dev/null; then
    echo "✅ La génération du schéma fonctionne"
else
    echo "❌ Erreur lors de la génération du schéma"
    python manage.py spectacular --format openapi-json 2>&1 | tail -20
fi