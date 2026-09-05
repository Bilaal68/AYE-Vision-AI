from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == user.Roles.ADMIN)


class IsAnalystOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in (user.Roles.ADMIN, user.Roles.ANALYST)


class IsViewerReadOnly(BasePermission):
    """Viewers may GET/HEAD/OPTIONS; analysts and admins may write."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.role in (user.Roles.ADMIN, user.Roles.ANALYST)
