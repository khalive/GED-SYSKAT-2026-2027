from .models import JournalAudit

# cette fonction est utilisée pour obtenir l'adresse IP du client à partir de la requête HTTP. Elle vérifie d'abord si l'en-tête "HTTP_X_FORWARDED_FOR" est présent, ce qui indique que la requête a été transmise par un proxy (comme Nginx). Si cet en-tête est présent, elle renvoie la première adresse IP de la liste (qui est généralement l'adresse IP du client d'origine). Si l'en-tête n'est pas présent, elle renvoie l'adresse IP directe du client à partir de "REMOTE_ADDR".
def get_client_ip(request):
    """Adresse IP du client (tient compte d'un proxy type Nginx)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

# Cette fonction est utilisée pour enregistrer une action dans le journal d'audit. Elle prend en paramètres la requête HTTP, l'action effectuée, l'utilisateur (optionnel), l'entité cible (optionnelle), l'identifiant de la cible (optionnel) et les détails supplémentaires (optionnels). Si l'utilisateur n'est pas fourni et que l'utilisateur de la requête est authentifié, il utilise cet utilisateur. Ensuite, elle crée une nouvelle entrée dans le modèle JournalAudit avec les informations fournies, y compris l'adresse IP du client obtenue à partir de la fonction get_client_ip.
def journaliser(request, action, utilisateur=None, entite="", id_cible=None, details=None):
    """Écrit une ligne dans le journal d'audit."""
    if utilisateur is None and request.user.is_authenticated:
        utilisateur = request.user
    return JournalAudit.objects.create(
        utilisateur=utilisateur,
        action=action,
        entite_cible=entite,
        id_cible=id_cible,
        adresse_ip=get_client_ip(request),
        details=details or {},
    )