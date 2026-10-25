import ipaddress

from .models import AuditLog


class AuditService:
    """
    Centralise l'écriture du journal d'activité.

    Le service accepte soit un objet cible (target), soit
    directement target_type/target_id/target_repr. Ce second
    mode est utile lorsque l'objet vient d'être supprimé et
    que sa clé primaire a été remise à None par Django.
    """

    @staticmethod
    def _extract_ip(request):
        if request is None:
            return None

        forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        value = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

        if not value:
            return None

        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None

    @classmethod
    def log(
        cls,
        *,
        action,
        actor=None,
        target=None,
        target_type="",
        target_id="",
        target_repr="",
        changes=None,
        metadata=None,
        request=None,
    ):
        if request is not None:
            request_user = getattr(
                request,
                "user",
                None,
            )

            if (
                actor is None
                and request_user is not None
                and request_user.is_authenticated
            ):
                actor = request_user

        if actor is not None and not getattr(
            actor,
            "is_authenticated",
            False,
        ):
            actor = None

        if target is not None:
            opts = target._meta

            target_type = (
                f"{opts.app_label}.{opts.model_name}"
            )
            target_id = (
                str(target.pk)
                if target.pk is not None
                else ""
            )
            target_repr = str(target)

        user_agent = ""

        if request is not None:
            user_agent = request.META.get(
                "HTTP_USER_AGENT",
                "",
            )[:500]

        return AuditLog.objects.create(
            actor=actor,
            actor_email=(
                getattr(actor, "email", "")
                if actor is not None
                else ""
            ),
            action=action,
            target_type=target_type[:100],
            target_id=target_id[:64],
            target_repr=target_repr[:255],
            changes=changes or {},
            metadata=metadata or {},
            ip_address=cls._extract_ip(request),
            user_agent=user_agent,
        )
