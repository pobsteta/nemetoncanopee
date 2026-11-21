#!/bin/sh
# Tests de release-necessaire.sh : cas synthétiques dans un dépôt temporaire.
S="$(cd "$(dirname "$0")" && pwd)/release-necessaire.sh"
ECHECS=0
verifie() { # nom attendu obtenu
  case "$3" in "$2"*) echo "ok   $1";; *) echo "ECHEC $1 : attendu '$2', obtenu '$3'"; ECHECS=$((ECHECS+1));; esac
}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cd "$T" && git init -q . && git config user.email t@t && git config user.name t
commit() { git add -A && git commit -q -m "$1"; }
ecrit() { mkdir -p "$(dirname "$1")"; echo "$2" >> "$1"; }

ecrit src/nemeton_canopee/a.py 1; commit init
verifie "aucun tag" "release:" "$("$S")"
git tag v2026.11.1
verifie "rien changé" "pas de release:" "$("$S")"
ecrit docs/adr/0001.md x; ecrit docs/a.pdf x; ecrit README.md x; ecrit BRIEF.md x; commit docs
verifie "seulement docs/md" "pas de release:" "$("$S")"
ecrit src/nemeton_canopee/a.py 2; commit code
verifie "docs + code" "release:" "$("$S")"
git tag -f v2026.11.1 HEAD >/dev/null
ecrit .github/badges/coverage.svg x; commit badge
verifie "badge seul" "pas de release:" "$("$S")"
ecrit .github/workflows/release.yml x; commit workflow
verifie "workflow modifié" "release:" "$("$S")"
# code non publié, puis fusion de docs : on compare au tag, pas au commit précédent
git tag v2026.11.2; ecrit src/nemeton_canopee/b.py 1; commit code2; ecrit docs/j.md x; commit docs2
verifie "code puis docs (CI annulée)" "release:" "$("$S")"
verifie "commit inconnu" "release:" "$("$S" deadbeef)"

# tête de main et fichiers de test
CODE2=$(git rev-parse HEAD)
verifie "commit = tête de main" "release:" "$("$S" HEAD "" "$CODE2")"
ecrit src/nemeton_canopee/b.py 2; commit code3
verifie "commit dépassé par la tête" "pas de release: commit dépassé par $(printf '%s' "$(git rev-parse HEAD)" | cut -c1-7)" "$("$S" "$CODE2" "" "$(git rev-parse HEAD)")"
verifie "tête inconnue localement (SHA brut)" "pas de release: commit dépassé par 1234567" "$("$S" HEAD "" 1234567890abcdef1234567890abcdef12345678)"
verifie "tête illisible : on publie" "release:" "$("$S" HEAD)"
git tag v2026.11.3
ecrit tests/test_x.py x; ecrit tests/data/z.json x
ecrit .github/scripts/test-release-necessaire.sh x; commit tests
verifie "tests seuls" "pas de release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"
ecrit src/nemeton_canopee/c.py 1; commit "test + code"
verifie "tests + code" "release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"
git tag v2026.11.4
ecrit tests/test_q.py x; ecrit .github/scripts/release-necessaire.sh x; commit "test + script de release"
verifie "le script de release lui-même compte" "release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"
git tag v2026.11.5
ecrit pyproject.toml x; commit "dépendances"
verifie "pyproject.toml compte" "release:" "$("$S" HEAD "" "$(git rev-parse HEAD)")"

# la CI pousse un commit de badge [skip ci] sur main après le commit de code
git tag v2026.11.6; ecrit src/nemeton_canopee/d.py 1; commit "code D"; CODED=$(git rev-parse HEAD)
ecrit .github/badges/coverage.svg y; commit "docs: mise à jour du badge de couverture [skip ci]"; BADGE=$(git rev-parse HEAD)
verifie "code puis badge [skip ci] : release" "release:" "$("$S" "$CODED" "" "$BADGE")"
ecrit docs/n.md x; commit "docs"; DOCS=$(git rev-parse HEAD)
verifie "code puis badge puis docs : release" "release:" "$("$S" "$CODED" "" "$DOCS")"
ecrit tests/test_r.py x; commit "tests"; TESTS=$(git rev-parse HEAD)
verifie "code puis tests : release" "release:" "$("$S" "$CODED" "" "$TESTS")"
ecrit src/nemeton_canopee/e.py 1; commit "code E"; CODEE=$(git rev-parse HEAD)
verifie "code puis badge puis code : dépassé" "pas de release: commit dépassé par $(printf '%s' "$CODEE" | cut -c1-7)" "$("$S" "$CODED" "" "$CODEE")"

if [ "$ECHECS" -eq 0 ]; then echo "Tous les tests passent."; else echo "$ECHECS échec(s)."; exit 1; fi
