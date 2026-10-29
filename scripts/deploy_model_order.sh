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
TENANT_URL[myia]="$MYIA_URL"; TENANT_EMAIL[myia]="$MYIA_EMAIL"; TENANT_PASS[myia]="$MYIA_PASSWORD"
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

# Delete a legacy model if it exists (POST /models/model/delete with {id} in body)
delete_model_if_exists() {
    local url=$1 token=$2 model_id=$3
    local http_code
    http_code=$(curl -sk "$url/api/v1/models/model?id=$model_id" \
        -H "Authorization: Bearer $token" -o /dev/null -w "%{http_code}")
    if [ "$http_code" = "200" ]; then
        local result
        result=$(curl -sk -X POST "$url/api/v1/models/model/delete" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "{\"id\":\"$model_id\"}" -o /dev/null -w "%{http_code}")
        echo "  $model_id: deleted (HTTP $result)"
    fi
}

ORDER=$(cat "$ORDER_JSON")

for tenant in myia epf epita esg ece epf-genai pauwels; do
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

    # 2. Deploy custom models with calibrated sampling params (2026-03-21)
    # Params calibrated from: Qwen official + Reddit r/LocalLLaMA + AWQ Q4 benchmarks
    # Convention: top_k, repetition_penalty, chat_template_kwargs go in custom_params (not native OWUI OpenAI mappings)
    # Rule: NO presence_penalty or repetition_penalty for coding-oriented profiles

    create_or_update_model "$URL" "$TOKEN" "Local.qwen3.6-35b-a3b" \
        '{"id":"Local.qwen3.6-35b-a3b","name":"Qwen3.6-35B-A3B (Thinking)","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":0.7,"presence_penalty":1.5,"top_p":0.95,"custom_params":{"top_k":20,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Qwen3.6-35B-A3B avec thinking activé. Paramètres calibrés pour AWQ Q4 (temp 0.7, pp 1.5). Local et gratuit. Contexte 262K tokens.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "Local.qwen3.6-35b-a3b-fast" \
        '{"id":"Local.qwen3.6-35b-a3b-fast","name":"Qwen3.6-35B-A3B (Fast)","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":0.6,"top_p":0.85,"min_p":0.01,"presence_penalty":0.5,"max_tokens":4096,"custom_params":{"top_k":20,"repetition_penalty":1.1,"chat_template_kwargs":{"enable_thinking":false}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Version rapide de Qwen3.6-35B sans réflexion interne. Réponses directes en 1-3 secondes. Local et gratuit. Contexte 262K tokens. Idéal pour : questions simples, traductions, reformulations, conversations rapides.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "expert-analyste" \
        '{"id":"expert-analyste","name":"Expert Analyste","base_model_id":"Local.qwen3.6-35b-a3b","params":{"system":"Tu es un analyste expert français, rigoureux et méthodique.\n\n## Ton rôle\n- Tu décomposes les problèmes complexes en sous-parties claires\n- Tu structures tes analyses avec des tableaux, bullet points et sections numérotées\n- Tu identifies les forces, faiblesses, opportunités et menaces\n- Tu conclus toujours par une recommandation actionnable\n\n## Ton style\n- Précis et factuel, évite les généralités\n- Utilise des données chiffrées quand possible\n- Présente les différents points de vue avant de conclure\n- Réponds en français sauf si l'\''utilisateur écrit en anglais","temperature":0.6,"presence_penalty":0.0,"top_p":0.95,"custom_params":{"top_k":20,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Analyste structuré français. Décompose les problèmes complexes en étapes, produit des analyses claires avec sections numérotées. Basé sur Qwen3.6-35B (local, gratuit, rapide). Idéal pour : études de cas, comparaisons, synthèses argumentées.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "redacteur-technique" \
        '{"id":"redacteur-technique","name":"Rédacteur Technique","base_model_id":"Local.qwen3.6-35b-a3b","params":{"system":"Tu es un rédacteur technique professionnel français.\n\n## Ton rôle\n- Tu rédiges de la documentation technique claire, structurée et pédagogique\n- Tu maîtrises le Markdown, les diagrammes et la mise en page\n- Tu adaptes ton niveau technique au public cible\n- Tu inclus des exemples concrets et des cas d'\''usage\n\n## Ton style\n- Structure hiérarchique claire (titres, sous-titres, listes)\n- Phrases courtes et directes\n- Vocabulaire technique précis avec définitions si nécessaire\n- Réponds en français sauf si l'\''utilisateur écrit en anglais","temperature":0.8,"presence_penalty":0.5,"top_p":0.95,"min_p":0.05,"custom_params":{"top_k":20,"repetition_penalty":1.05,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Rédacteur de documentation technique en français. Produit des guides, procédures, rapports et spécifications structurés. Basé sur Qwen3.6-35B (local, gratuit, rapide). Idéal pour : rédaction de docs, tutoriels, comptes-rendus, manuels.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "vision-expert" \
        '{"id":"vision-expert","name":"Expert Vision","base_model_id":"Local.omnicoder-9b","params":{"system":"Tu es un expert en analyse visuelle. Tu analyses les images avec rigueur et précision.\n\nPour chaque image:\n1. **Description factuelle**: Décris ce que tu vois objectivement\n2. **Éléments clés**: Identifie les éléments importants (texte, diagrammes, données)\n3. **Interprétation**: Donne ton analyse du contexte et de la signification\n4. **Détails techniques**: Si applicable, extrais les données, mesures, ou structures\n\nRéponds en français. Sois précis sur les positions, couleurs, textes visibles.","temperature":0.2},"meta":{"profile_image_url":"/static/favicon.png","description":"Spécialiste analyse d'\''images et documents visuels. Décrit, interprète et extrait les données des photos, diagrammes, captures d'\''écran et schémas. Basé sur OmniCoder-9B (local, gratuit). Idéal pour : OCR, analyse de graphiques, description d'\''images.","capabilities":{"vision":true}}}'

    # 3. Deploy Qwen_* sampling profiles (calibrated 2026-03-21)
    create_or_update_model "$URL" "$TOKEN" "Qwen_think" \
        '{"id":"Qwen_think","name":"Qwen 3.6 Think (Général)","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":0.7,"presence_penalty":1.5,"top_p":0.95,"max_tokens":8192,"custom_params":{"top_k":20,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Qwen3.6-35B thinking mode, sampling optimisé général (temp 0.7, pp 1.5). Calibré AWQ Q4.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "Qwen_think-code" \
        '{"id":"Qwen_think-code","name":"Qwen 3.6 Think Code","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":0.6,"presence_penalty":0.0,"top_p":0.95,"max_tokens":16384,"custom_params":{"top_k":20,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Qwen3.6-35B thinking mode optimisé code (temp 0.6, pas de pénalité). Preset officiel Qwen.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "Qwen_think-reason" \
        '{"id":"Qwen_think-reason","name":"Qwen 3.6 Think Reason","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":1.0,"presence_penalty":1.5,"top_p":1.0,"max_tokens":16384,"custom_params":{"top_k":40,"chat_template_kwargs":{"enable_thinking":true}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Qwen3.6-35B thinking mode raisonnement profond (temp 1.0, pp 1.5, top_k 40). Max diversité.","capabilities":null}}'

    create_or_update_model "$URL" "$TOKEN" "Qwen_instruct" \
        '{"id":"Qwen_instruct","name":"Qwen 3.6 Instruct (Chat rapide)","base_model_id":"Local.qwen3.6-35b-a3b","params":{"temperature":0.7,"presence_penalty":1.5,"top_p":0.8,"min_p":0.01,"max_tokens":4096,"custom_params":{"top_k":20,"repetition_penalty":1.1,"chat_template_kwargs":{"enable_thinking":false}}},"meta":{"profile_image_url":"/static/favicon.png","description":"Qwen3.6-35B mode instruct sans thinking. Réponses rapides, anti-bleed Q4 (rp 1.1).","capabilities":null}}'

    # 4. Cleanup legacy Qwen3.5 wrappers (run AFTER creates/updates so personas
    # briefly point to a valid base, then the legacy ids get removed safely)
    delete_model_if_exists "$URL" "$TOKEN" "Local.qwen3.5-35b-a3b-fast"
    delete_model_if_exists "$URL" "$TOKEN" "Local.qwen3.5-35b-a3b"

    echo "  Done."
done

echo ""
echo "=== Deployment complete ==="
