from decimal import Decimal


class ExportPDF:
    def __init__(self, bulletin, employe=None):
        self.bulletin = bulletin
        self.employe = employe

    def generer(self, fichier=None):
        if fichier:
            self._generer_pdf(fichier)
            return fichier
        return self._generer_contenu_html()

    def _generer_contenu_html(self):
        nom_employe = self.employe if self.employe else self.bulletin.employe_id
        lignes_html = ""
        for ligne in self.bulletin.lignes:
            lignes_html += f"""
            <tr>
                <td>{ligne.rubrique_code}</td>
                <td style="text-align:right">{int(ligne.base):,} F</td>
                <td style="text-align:right">{float(ligne.taux)*100:.1f}%</td>
                <td style="text-align:right">{int(ligne.montant):,} F</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Bulletin de paie</title></head>
<body>
<h2>Bulletin de paie</h2>
<p><strong>Employé :</strong> {nom_employe}</p>
<p><strong>Période :</strong> {self.bulletin.periode}</p>
<p><strong>Date d'édition :</strong> {self.bulletin.date_edition}</p>
<table border="1" cellpadding="5" style="border-collapse:collapse;width:100%">
<tr><th>Rubrique</th><th>Base</th><th>Taux</th><th>Montant</th></tr>
{lignes_html}
<tr style="font-weight:bold">
    <td colspan="3">Total gains</td>
    <td style="text-align:right">{int(self.bulletin.total_gains()):,} F</td>
</tr>
<tr style="font-weight:bold">
    <td colspan="3">Total retenues</td>
    <td style="text-align:right">{int(self.bulletin.total_retenues()):,} F</td>
</tr>
<tr style="font-weight:bold;background-color:#e8f5e9">
    <td colspan="3">Net à payer</td>
    <td style="text-align:right">{int(self.bulletin.net_a_payer()):,} F</td>
</tr>
</table>
</body></html>"""

    def _generer_pdf(self, fichier):
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(fichier, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"Bulletin de paie - {self.bulletin.periode}", styles["Title"]))
        nom = self.employe if self.employe else self.bulletin.employe_id
        elements.append(Paragraph(f"Employé : {nom}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        data = [["Rubrique", "Base (F CFA)", "Taux", "Montant (F CFA)"]]
        for ligne in self.bulletin.lignes:
            data.append([
                ligne.rubrique_code,
                f"{int(ligne.base):,}",
                f"{float(ligne.taux)*100:.1f}%",
                f"{int(ligne.montant):,}",
            ])
        data.append(["", "", "Total gains", f"{int(self.bulletin.total_gains()):,}"])
        data.append(["", "", "Total retenues", f"{int(self.bulletin.total_retenues()):,}"])
        data.append(["", "", "Net à payer", f"{int(self.bulletin.net_a_payer()):,}"])

        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -3), 0.5, colors.black),
            ("BACKGROUND", (2, -1), (-1, -1), colors.lightgreen),
        ]))
        elements.append(table)
        doc.build(elements)


def generer_bulletin_pdf(bulletin, employe, chemin):
    export = ExportPDF(bulletin, employe)
    return export.generer(chemin)
