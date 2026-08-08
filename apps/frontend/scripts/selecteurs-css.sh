#!/usr/bin/env bash
# Liste les classes CSS effectivement produites par le build, une par ligne.
#
# Sert a comparer deux builds : une classe qui disparait du CSS ne se voit pas
# forcement a l'ecran (elle peut ne rien changer sur la page qu'on a capturee),
# mais elle cassera la page ou elle sert. Le diff de cette liste attrape ce
# qu'une capture manque.
set -euo pipefail
cat "$@" | tr '{},' '\n\n\n' | tr -d '\\' | grep -oE '\.[a-zA-Z][a-zA-Z0-9_:./%!-]*' | sort -u
