#!/bin/bash
# Deploy MODEL_ORDER_LIST and custom models to all tenants
# Usage: bash scripts/deploy_model_order.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ORDER_JSON="$SCRIPT_DIR/model_order.json"

# Source credentials
source "$SCRIPT_DIR/../.env"

# Tenants to deploy to
declare -A TENANT_URL TENANT_EMAIL TENANT_PASS
TENANT_URL[epf]="$EPF_URL"; TENANT_EMAIL[epf]="$EPF_EMAIL"; TENANT_PASS[epf]="$EPF_PASSWORD"
TENANT_URL[epita]="$EPITA_URL"; TENANT_EMAIL[epita]="$EPITA_EMAIL"; TENANT_PASS[epita]="$EPITA_PASSWORD"
TENANT_URL[esg]="$ESG_URL"; TENANT_EMAIL[esg]="$ESG_EMAIL"; TENANT_PASS[esg]="$ESG_PASSWORD"
TENANT_URL[ece]="$ECE_URL"; TENANT_EMAIL[ece]="$ECE_EMAIL"; TENANT_PASS[ece]="$ECE_PASSWORD"
TENANT_URL[epf-genai]="$EPF_GENAI_URL"; TENANT_EMAIL[epf-genai]="$EPF_GENAI_EMAIL"; TENANT_PASS[epf-genai]="$EPF_GENAI_PASSWORD"
TENANT_URL[pauwels]="$PAUWELS_URL"; TENANT_EMAIL[pauwels]="$PAUWELS_EMAIL"; TENANT_PASS[pauwels]="$PAUWELS_PASSWORD"

authenticate() {
    local url=$1 email=$2 password=$3
    curl -sk -X POST "$url/api/v1/auths/signin" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}" | \
        grep -o '"token":"[^"]*"' | cut -d'"' -f4
}

# Create or update a model
create_or_update_model() {
    local url=$1 token=$2 model_id=$3 payload=$4

    # Check if model exists
    local http_code
    http_code=$(curl -sk "$url/api/v1/models/model?id=$model_id" \
        -H "Authorization: Bearer $token" -o /dev/null -w "%{http_code}")

    if [ "$http_code" = "200" ]; then
        # Update existing
        local result
        result=$(curl -sk -X POST "$url/api/v1/models/model/update" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "$payload" -o /dev/null -w "%{http_code}")
        echo "  $model_id: updated (HTTP $result)"
    else
        # Create new
        local result
        result=$(curl -sk -X POST "$url/api/v1/models/create" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "$payload" -o /dev/null -w "%{http_code}")
        echo "  $model_id: created (HTTP $result)"
    fi
}

ORDER=$(cat "$ORDER_JSON")

for tenant in epf epita esg ece epf-genai pauwels; do
    URL="${TENANT_URL[$tenant]}"
    EMAIL="${TENANT_EMAIL[$tenant]}"
    PASSWORD="${TENANT_PASS[$tenant]}"
    echo ""
    echo "=== $tenant ($URL) ==="

    # Authenticate
    TOKEN=$(authenticate "$URL" "$EMAIL" "$PASSWORD")
    if [ -z "$TOKEN" ]; then
        echo "  FAILED: Could not authenticate"
        continue
    fi
    echo "  Authenticated OK"

    # 1. Deploy MODEL_ORDER_LIST
    RESULT=$(curl -sk -X POST "$URL/api/v1/configs/models" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"DEFAULT_MODELS\":\"samantha\",\"DEFAULT_PINNED_MODELS\":null,\"MODEL_ORDER_LIST\":$ORDER}" \
        -o /dev/null -w "%{http_code}")
    echo "  MODEL_ORDER_LIST: HTTP $RESULT"

    # 2. Deploy custom models
    create_or_update_model "$URL" "$TOKEN" "expert-analyste" \
        '{"id":"expert-analyste","name":"Expert Analyste","base_model_id":"Local.qwen3.5-35b-a3b","params":{},"meta":{"profile_image_url":"/static/favicon.png","description":"Analyste structuré français. Décompose les problèmes complexes en étapes, produit des analyses claires avec sections numérotées. Basé sur Qwen3.5-35B (local, gratuit, rapide). Idéal pour : études de cas, comparaisons, synthèses argumentées.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "redacteur-technique" \
        '{"id":"redacteur-technique","name":"Rédacteur Technique","base_model_id":"Local.qwen3.5-35b-a3b","params":{},"meta":{"profile_image_url":"/static/favicon.png","description":"Rédacteur de documentation technique en français. Produit des guides, procédures, rapports et spécifications structurés. Basé sur Qwen3.5-35B (local, gratuit, rapide). Idéal pour : rédaction de docs, tutoriels, comptes-rendus, manuels.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "vision-expert" \
        '{"id":"vision-expert","name":"Expert Vision","base_model_id":"Local.zwz-8b","params":{"system":"Tu es un expert en analyse visuelle. Tu analyses les images avec rigueur et précision.\n\nPour chaque image:\n1. **Description factuelle**: Décris ce que tu vois objectivement\n2. **Éléments clés**: Identifie les éléments importants (texte, diagrammes, données)\n3. **Interprétation**: Donne ton analyse du contexte et de la signification\n4. **Détails techniques**: Si applicable, extrais les données, mesures, ou structures\n\nRéponds en français. Sois précis sur les positions, couleurs, textes visibles.","temperature":0.2},"meta":{"profile_image_url":"/static/favicon.png","description":"Spécialiste analyse d'\''images et documents visuels. Décrit, interprète et extrait les données des photos, diagrammes, captures d'\''écran et schémas. Basé sur ZwZ-8B Vision (local, gratuit). Idéal pour : OCR, analyse de graphiques, description d'\''images.","capabilities":{"vision":true}}}'

    create_or_update_model "$URL" "$TOKEN" "Local.qwen3.5-35b-a3b-fast" \
        '{"id":"Local.qwen3.5-35b-a3b-fast","name":"Qwen3.5-35B-A3B (Fast)","base_model_id":"Local.qwen3.5-35b-a3b","params":{"custom_params":{"chat_template_kwargs":{"enable_thinking":false}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Version rapide de Qwen3.5-35B sans réflexion interne. Réponses directes en 1-3 secondes. Local et gratuit. Contexte 262K tokens. Idéal pour : questions simples, traductions, reformulations, conversations rapides.","capabilities":null}}'

    echo "  Done."
done

echo ""
echo "=== Deployment complete ==="
