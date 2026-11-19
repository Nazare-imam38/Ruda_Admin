from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('layers', '0002_physical_tables_and_fields')]
    operations = [
        migrations.AddField(model_name='layer', name='publication', field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name='layer', name='publication_history', field=models.JSONField(default=list, blank=True)),
    ]
