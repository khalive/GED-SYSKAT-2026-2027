from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_profils_et_permissions_initiaux"),
        ("documents", "0003_document_emplacement"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossier",
            name="roles_autorises",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Si vide, le dossier hérite des restrictions du type de document "
                    "et de ses parents."
                ),
                related_name="dossiers",
                to="accounts.role",
            ),
        ),
    ]
