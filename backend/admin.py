from sqladmin import Admin, ModelView

from backend.db import engine
from backend.models_db import Task, Download, MediaFile, Setting


class TaskAdmin(ModelView, model=Task):
    name_plural = "Tasks"
    icon = "fa-solid fa-list-check"
    column_list = [
        Task.id, Task.type, Task.status, Task.progress,
        Task.message, Task.created_at, Task.started_at, Task.finished_at,
    ]
    column_searchable_list = [Task.id, Task.type, Task.message]
    column_sortable_list = [Task.created_at, Task.started_at, Task.finished_at, Task.status]
    column_default_sort = [(Task.created_at, True)]
    column_filters = [Task.status, Task.type]


class DownloadAdmin(ModelView, model=Download):
    name_plural = "Downloads"
    icon = "fa-solid fa-download"
    column_list = [
        Download.id, Download.title, Download.source, Download.url,
        Download.requested_quality, Download.task_id, Download.created_at,
    ]
    column_searchable_list = [Download.title, Download.url, Download.source]
    column_sortable_list = [Download.created_at]
    column_default_sort = [(Download.created_at, True)]
    column_filters = [Download.source]


class MediaFileAdmin(ModelView, model=MediaFile):
    name_plural = "Media Files"
    icon = "fa-solid fa-film"
    column_list = [
        MediaFile.id, MediaFile.filename, MediaFile.kind, MediaFile.container,
        MediaFile.size_bytes, MediaFile.duration_sec, MediaFile.width, MediaFile.height,
        MediaFile.created_at,
    ]
    column_searchable_list = [MediaFile.filename, MediaFile.path, MediaFile.source_url]
    column_sortable_list = [MediaFile.created_at, MediaFile.size_bytes, MediaFile.duration_sec]
    column_default_sort = [(MediaFile.created_at, True)]
    column_filters = [MediaFile.kind, MediaFile.container]


class SettingAdmin(ModelView, model=Setting):
    name_plural = "Settings"
    icon = "fa-solid fa-gear"
    column_list = [Setting.key, Setting.value]
    column_searchable_list = [Setting.key]


def setup_admin(app):
    admin = Admin(app, engine, title="Video Downloader Admin", base_url="/admin")
    admin.add_view(TaskAdmin)
    admin.add_view(DownloadAdmin)
    admin.add_view(MediaFileAdmin)
    admin.add_view(SettingAdmin)
    return admin
