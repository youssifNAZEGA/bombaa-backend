from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Pagination commune à l'API BOMBAA.

    Le client peut demander une taille de page via ?page_size=,
    dans la limite de 100 éléments.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
