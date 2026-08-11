# -*- coding: utf-8 -*-
# 繞過 Django 針對 MySQL 8.4+ 的版本檢查限制，全面向下相容 MySQL 8.0.x (如 8.0.39)
try:
    from django.db.backends.mysql import base as mysql_base
    mysql_base.DatabaseWrapper.check_database_version_supported = lambda self: None
except Exception:
    pass
