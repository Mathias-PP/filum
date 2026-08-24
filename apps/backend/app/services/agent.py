    try:
        # Utiliser le quota_tours si défini dans agent_def, sinon utiliser MAX_TOURS
        quota_tours = agent_def.quota_tours if agent_def else MAX_TOURS
        for tour in range(1, quota_tours + 1):
            async def _on_delta(content: str, _t: int = tour) -> None:
                await emit({"type": "message_delta", "payload": {"delta": content, "tour": _t}})

            reponse = await _appel_provider(
                provider, messages, outils_api, transport, on_delta=_on_delta, modele=modele
            )
            if isinstance(reponse, str):
                if not rejeu_fait and _est_contexte_sature(reponse):
                    reduits, retires = compacter(messages, BUDGET_APRES_REFUS)
                    rejeu_fait = True
                    if retires:
                        messages[:] = reduits
                        await emit({"type": "contexte_compacte", "payload": {"messages_retires": retires}})
                        continue
                await emit({"type": "error", "payload": {"message": reponse}})
                return
            message, finish_reason, usage = reponse
            if isinstance(usage, dict):
                usage_total["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                usage_total["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                texte = _texte_message(message)
                if texte:
                    await emit({"type": "done", "payload": {"reason": "complete", "usage": usage_total}})
                    return
                logger.warning(
                    "Reponse vide du provider %s modele=%s finish_reason=%s usage=%s",
                    provider.provider,
                    provider.model,
                    finish_reason,
                    usage,
                )
                await emit({
                    "type": "error",
                    "payload": {
                        "message": _diagnostic_vide(provider.model, finish_reason, usage)
                    },
                })
                return
            messages.append({
                "role": "assistant",
                "content": _texte_message(message) or None,
                "tool_calls": tool_calls,
            })
            await _executer_tour(db, user, tour, messages, tool_calls, registre, emit, approuver)
            # Vérification du quota
            if tour >= quota_tours:
                compactes, retires = compacter(messages, BUDGET_APRES_REFUS)
                messages[:] = compactes
                await emit({"type": "contexte_compacte", "payload": {"messages_retires": retires}})
                await emit({
                    "type": "continuation",
                    "payload": {
                        "message": f'Pause après {quota_tours} actions : l\'agent a beaucoup travaillé et peut continuer. Cliquez sur Continuer ou envoyez "continue".',
                        "tours": quota_tours,
                    }
                })
        # Limite atteinte : pas une erreur dure, mais une pause avec reprise.
        compactes, retires = compacter(messages, BUDGET_APRES_REFUS)
        if retires:
            messages[:] = compactes
            await emit({"type": "contexte_compacte", "payload": {"messages_retires": retires}})
        # Émettre une continuation unique pour éviter la duplication
        await emit({
            "type": "continuation",
            "payload": {
                "message": f'Pause après {quota_tours} actions : l\'agent a beaucoup travaillé et peut continuer. Cliquez sur Continuer ou envoyez "continue".',
                "tours": quota_tours,
            }
        })