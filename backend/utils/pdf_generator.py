"""
PDF Report Generation using ReportLab.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from typing import Dict, Any
import os

from models.schemas import FinalReport


class PDFReportGenerator:
    """Generate PDF reports from analysis results."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Recommendation style
        self.styles.add(ParagraphStyle(
            name='Recommendation',
            parent=self.styles['Heading1'],
            fontSize=36,
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#334155'),
            spaceAfter=12,
            spaceBefore=20
        ))
    
    def generate_pdf(self, report: FinalReport, output_path: str) -> str:
        """
        Generate PDF report.
        
        Args:
            report: FinalReport object
            output_path: Path to save PDF
        
        Returns:
            Path to generated PDF
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build content
        story = []
        
        # Header
        story.append(Paragraph("EQUITY RESEARCH REPORT", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"{report.company_name or report.ticker} ({report.ticker})",
            self.styles['Heading2']
        ))
        story.append(Paragraph(
            f"Analysis Date: {report.analysis_date.strftime('%B %d, %Y')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.3*inch))
        
        # Recommendation Box
        rec_color = self._get_recommendation_color(report.recommendation)
        story.append(Paragraph(
            f'<font color="{rec_color}">{report.recommendation}</font>',
            self.styles['Recommendation']
        ))
        story.append(Paragraph(
            f"Score: {report.final_score:.1f}/100 | Confidence: {report.confidence:.0%}",
            self.styles['Heading3']
        ))
        story.append(Spacer(1, 0.3*inch))
        
        # Executive Summary
        if report.xai_explanation:
            story.append(Paragraph("Executive Summary", self.styles['SectionHeading']))
            # Extract just the executive summary part
            summary_text = report.xai_explanation.split('---')[0] if '---' in report.xai_explanation else report.xai_explanation
            import re
            clean_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', summary_text)
            clean_text = clean_text.replace('**', '')  # strip any leftover unpaired markers
            story.append(Paragraph(clean_text, self.styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
        
        # Agent Scores Table
        story.append(Paragraph("Agent Analysis Summary", self.styles['SectionHeading']))
        agent_data = [['Agent', 'Score', 'Confidence', 'Assessment']]
        
        for agent_name, score in [
            ('Fundamental', report.fundamental_score),
            ('Technical', report.technical_score),
            ('Sentiment', report.sentiment_score),
            ('Governance', report.governance_score),
            ('PEAD', report.pead_score),
            ('Financial Health', report.financial_health_score),
            ('Risk', report.risk_score),
            ('Macro', report.macro_score),
            ('Insider', report.insider_score)
        ]:
            if score:
                assessment = 'Strong' if score.score >= 70 else 'Moderate' if score.score >= 50 else 'Weak'
                agent_data.append([
                    agent_name,
                    f"{score.score:.1f}",
                    f"{score.confidence:.0%}",
                    assessment
                ])
        
        agent_table = Table(agent_data, colWidths=[2*inch, 1*inch, 1*inch, 1.5*inch])
        agent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(agent_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Detailed Analysis
        story.append(PageBreak())
        story.append(Paragraph("Detailed Analysis", self.styles['SectionHeading']))
        
        for agent_name, score in [
            ('Fundamental Analyst', report.fundamental_score),
            ('Technical Analyst', report.technical_score),
            ('Sentiment Analyst', report.sentiment_score),
            ('Governance & Fraud', report.governance_score),
            ('PEAD Analyst', report.pead_score),
            ('RAG Filing & Financial Health', report.financial_health_score),
            ('Risk Analyst', report.risk_score),
            ('Macro Economic Analyst', report.macro_score),
            ('Insider Trading Analyst', report.insider_score)
        ]:
            if score and score.explanation:
                story.append(Paragraph(f"<b>{agent_name}</b>", self.styles['Heading3']))
                story.append(Paragraph(score.explanation, self.styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
        
        # System Metrics
        story.append(PageBreak())
        story.append(Paragraph("System Metrics", self.styles['SectionHeading']))
        metrics_data = [
            ['Metric', 'Value'],
            ['Analysis Latency', f"{report.latency_seconds:.2f} seconds"],
            ['Error Count', str(report.error_count)],
            ['Data Freshness', f"{report.data_freshness_hours:.1f} hours"]
        ]
        metrics_table = Table(metrics_data, colWidths=[3*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Disclaimer
        story.append(Spacer(1, 0.5*inch))
        disclaimer = """
        <b>Disclaimer:</b> This report is generated by AI and should not be considered as financial advice. 
        The analysis is based on available data and algorithmic processing. Please consult with a qualified 
        financial advisor before making investment decisions. Past performance does not guarantee future results.
        """
        story.append(Paragraph(disclaimer, self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        return output_path
    
    def _get_recommendation_color(self, recommendation: str) -> str:
        """Get color for recommendation."""
        if recommendation == 'BUY':
            return '#10b981'  # Green
        elif recommendation == 'HOLD':
            return '#f59e0b'  # Orange
        else:
            return '#ef4444'  # Red


# Global instance
pdf_generator = PDFReportGenerator()
