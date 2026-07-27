from django import template

register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter. Usage: {{ value|split:"," }}"""
    return str(value).split(delimiter)
