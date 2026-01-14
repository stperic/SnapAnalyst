"""
Data Export Utilities - Excel Generation with README

Creates Excel files with:
- README sheet (comprehensive documentation)
- Data sheets (households, members, errors)
- Professional formatting
"""
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session, joinedload

from src.database.models import Household, HouseholdMember, QCError


class DataExporter:
    """Handles data exports to Excel format with README."""
    
    # Colors for formatting
    HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    SECTION_FILL = PatternFill(start_color="B8CCE4", end_color="B8CCE4", fill_type="solid")
    README_TITLE_FILL = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    TITLE_FONT = Font(bold=True, size=14, color="FFFFFF")
    SECTION_FONT = Font(bold=True, size=12)
    
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    def __init__(self, db: Session, data_mapping_path: Path):
        """
        Initialize exporter.
        
        Args:
            db: Database session
            data_mapping_path: Path to data_mapping.json
        """
        self.db = db
        self.data_mapping = self._load_mapping(data_mapping_path)
    
    def _load_mapping(self, path: Path) -> Dict[str, Any]:
        """Load data mapping JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_excel_export(self, fiscal_year: int = None, limit: int = None) -> BytesIO:
        """
        Create complete Excel export with README and data.
        
        Args:
            fiscal_year: Optional fiscal year filter
            limit: Optional row limit per table
            
        Returns:
            BytesIO buffer containing Excel file
        """
        wb = Workbook()
        
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])
        
        # 1. Create README sheet (first/default)
        self._create_readme_sheet(wb, fiscal_year, limit)
        
        # 2. Create data sheets
        self._create_households_sheet(wb, fiscal_year, limit)
        self._create_members_sheet(wb, fiscal_year, limit)
        self._create_errors_sheet(wb, fiscal_year, limit)
        
        # Save to buffer
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        return buffer
    
    def _create_readme_sheet(self, wb: Workbook, fiscal_year: int = None, limit: int = None):
        """Create comprehensive README sheet."""
        ws = wb.create_sheet("README", 0)  # First sheet
        ws.sheet_properties.tabColor = "4F81BD"  # Blue tab
        
        row = 1
        
        # Title
        ws.merge_cells(f'A{row}:E{row}')
        title_cell = ws[f'A{row}']
        title_cell.value = "SnapAnalyst Data Export - README"
        title_cell.font = self.TITLE_FONT
        title_cell.fill = self.README_TITLE_FILL
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[row].height = 25
        row += 2
        
        # Generation info
        ws[f'A{row}'] = "Generated:"
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row += 1
        
        if fiscal_year:
            ws[f'A{row}'] = "Fiscal Year:"
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = fiscal_year
            row += 1
        
        if limit:
            ws[f'A{row}'] = "Row Limit:"
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = f"{limit} rows per table"
            row += 1
        
        row += 1
        
        # Database Info
        self._add_section(ws, row, "Database Information")
        row += 1
        
        db_info = self.data_mapping.get('database', {})
        info_items = [
            ("Name", db_info.get('name', 'N/A')),
            ("Version", db_info.get('version', 'N/A')),
            ("Description", db_info.get('description', 'N/A')),
            ("Total Households", db_info.get('total_households', 'N/A')),
            ("Fiscal Years", ', '.join(map(str, db_info.get('fiscal_years_available', [])))),
            ("Data Source", db_info.get('data_source', 'N/A')),
        ]
        
        for label, value in info_items:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            row += 1
        
        row += 1
        
        # Sheet Descriptions
        self._add_section(ws, row, "Sheets in This Workbook")
        row += 1
        
        sheets_info = [
            ("README", "This sheet - Complete documentation and data dictionary"),
            ("Households", "Household case data (~50k rows per year)"),
            ("Members", "Individual household member data (~120k rows)"),
            ("QC_Errors", "Quality control errors/variances (~20k rows)"),
        ]
        
        for sheet_name, description in sheets_info:
            ws[f'A{row}'] = sheet_name
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = description
            row += 1
        
        row += 1
        
        # Table Columns
        for table_name in ['households', 'household_members', 'qc_errors']:
            self._add_table_columns(ws, row, table_name)
            row = ws.max_row + 2
        
        # Code Lookups
        self._add_code_lookups(ws, row)
        row = ws.max_row + 2
        
        # Relationships
        self._add_relationships(ws, row)
        
        # Auto-size columns
        for col in ['A', 'B', 'C', 'D', 'E']:
            ws.column_dimensions[col].width = 25
        ws.column_dimensions['C'].width = 50  # Description column wider
        
    def _add_section(self, ws, row: int, title: str):
        """Add a section header."""
        ws.merge_cells(f'A{row}:E{row}')
        cell = ws[f'A{row}']
        cell.value = title
        cell.font = self.SECTION_FONT
        cell.fill = self.SECTION_FILL
        cell.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[row].height = 20
    
    def _add_table_columns(self, ws, start_row: int, table_name: str):
        """Add table column definitions."""
        table_info = self.data_mapping.get('tables', {}).get(table_name, {})
        
        # Section header
        display_name = table_name.replace('_', ' ').title()
        self._add_section(ws, start_row, f"{display_name} Table - Column Definitions")
        row = start_row + 1
        
        # Table description
        ws[f'A{row}'] = "Description:"
        ws[f'A{row}'].font = Font(bold=True)
        ws.merge_cells(f'B{row}:E{row}')
        ws[f'B{row}'] = table_info.get('description', 'N/A')
        row += 1
        
        ws[f'A{row}'] = "Row Count:"
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = table_info.get('row_count', 'N/A')
        row += 2
        
        # Column headers
        headers = ['Column', 'Type', 'Description', 'Range', 'Example']
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col_idx)
            cell.value = header
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = self.THIN_BORDER
        
        row += 1
        
        # Column data
        columns = table_info.get('columns', {})
        for col_name, col_info in columns.items():
            ws[f'A{row}'] = col_name
            ws[f'B{row}'] = col_info.get('type', '')
            ws[f'C{row}'] = col_info.get('description', '')
            ws[f'D{row}'] = str(col_info.get('range', ''))
            ws[f'E{row}'] = str(col_info.get('example', ''))
            
            # Add borders
            for col_idx in range(1, 6):
                ws.cell(row=row, column=col_idx).border = self.THIN_BORDER
            
            row += 1
    
    def _add_code_lookups(self, ws, start_row: int):
        """Add code lookup tables."""
        self._add_section(ws, start_row, "Code Lookup Tables")
        row = start_row + 1
        
        ws[f'A{row}'] = "Use these tables to decode numeric codes in the data."
        row += 2
        
        code_lookups = self.data_mapping.get('code_lookups', {})
        
        for lookup_name, lookup_data in code_lookups.items():
            # Lookup name
            ws[f'A{row}'] = lookup_name.replace('_', ' ').title()
            ws[f'A{row}'].font = Font(bold=True, size=11)
            row += 1
            
            ws[f'A{row}'] = "Description:"
            ws[f'B{row}'] = lookup_data.get('description', 'N/A')
            row += 1
            
            ws[f'A{row}'] = "Source Field:"
            ws[f'B{row}'] = lookup_data.get('source_field', 'N/A')
            row += 1
            
            # Code table headers
            ws[f'A{row}'] = "Code"
            ws[f'B{row}'] = "Description"
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'].font = Font(bold=True)
            ws[f'A{row}'].fill = self.SECTION_FILL
            ws[f'B{row}'].fill = self.SECTION_FILL
            row += 1
            
            # Codes
            for code, description in lookup_data.items():
                if code not in ['description', 'source_field']:
                    ws[f'A{row}'] = str(code)
                    ws[f'B{row}'] = str(description)
                    row += 1
            
            row += 1
    
    def _add_relationships(self, ws, start_row: int):
        """Add table relationships."""
        self._add_section(ws, start_row, "Table Relationships")
        row = start_row + 1
        
        ws[f'A{row}'] = "How tables connect via foreign keys:"
        row += 2
        
        relationships = self.data_mapping.get('relationships', {})
        
        for rel_name, rel_info in relationships.items():
            ws[f'A{row}'] = rel_name.replace('_', ' ').title()
            ws[f'A{row}'].font = Font(bold=True)
            row += 1
            
            ws[f'A{row}'] = "Type:"
            ws[f'B{row}'] = rel_info.get('type', 'N/A')
            row += 1
            
            ws[f'A{row}'] = "Description:"
            ws[f'B{row}'] = rel_info.get('description', 'N/A')
            row += 1
            
            ws[f'A{row}'] = "Join:"
            ws[f'B{row}'] = rel_info.get('join', 'N/A')
            row += 2
    
    def _create_households_sheet(self, wb: Workbook, fiscal_year: int = None, limit: int = None):
        """Create households data sheet."""
        ws = wb.create_sheet("Households")
        ws.sheet_properties.tabColor = "00B050"  # Green
        
        # Get global filter
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        current_filter = filter_manager.get_filter()
        
        # Query data - ORDER BY case_id to get consistent ordering
        query = self.db.query(Household).order_by(Household.case_id, Household.fiscal_year)
        
        # Apply global state filter
        if current_filter.state:
            query = query.filter(Household.state_name == current_filter.state)
        
        # Apply fiscal year filter
        if fiscal_year:
            query = query.filter(Household.fiscal_year == fiscal_year)
        elif current_filter.fiscal_year:
            query = query.filter(Household.fiscal_year == current_filter.fiscal_year)
        
        # Apply limit
        if limit:
            # For limited exports, get evenly distributed sample
            # Filter by case_id pattern to get distribution
            query = query.limit(limit)
        
        households = query.all()
        
        if not households:
            ws['A1'] = "No data available"
            return
        
        # Headers
        columns = [
            'case_id', 'fiscal_year', 'state_code', 'state_name', 'year_month',
            'status', 'snap_benefit', 'raw_benefit', 'amount_error', 'gross_income',
            'net_income', 'earned_income', 'unearned_income', 'certified_household_size',
            'num_elderly', 'num_children', 'num_disabled', 'categorical_eligibility',
            'working_poor_indicator', 'tanf_indicator'
        ]
        
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal='center')
        
        # Data rows
        for row_idx, household in enumerate(households, 2):
            for col_idx, col_name in enumerate(columns, 1):
                value = getattr(household, col_name, None)
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        # Auto-size columns
        for col_idx in range(1, len(columns) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
    
    def _create_members_sheet(self, wb: Workbook, fiscal_year: int = None, limit: int = None):
        """Create household members data sheet."""
        ws = wb.create_sheet("Members")
        ws.sheet_properties.tabColor = "FFC000"  # Orange
        
        # Get global filter
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        current_filter = filter_manager.get_filter()
        
        # Query data - SELECT state_name directly from joined Household to avoid lazy loading
        query = self.db.query(
            HouseholdMember,
            Household.state_name
        ).join(
            Household,
            (HouseholdMember.case_id == Household.case_id) & 
            (HouseholdMember.fiscal_year == Household.fiscal_year)
        ).order_by(HouseholdMember.case_id, HouseholdMember.fiscal_year, HouseholdMember.member_number)
        
        # Apply global state filter
        if current_filter.state:
            query = query.filter(Household.state_name == current_filter.state)
        
        # Apply fiscal year filter
        if fiscal_year:
            query = query.filter(Household.fiscal_year == fiscal_year)
        elif current_filter.fiscal_year:
            query = query.filter(Household.fiscal_year == current_filter.fiscal_year)
        
        # Apply limit
        if limit:
            # Get distributed sample
            query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            ws['A1'] = "No data available"
            return
        
        # Headers
        columns = [
            'case_id', 'fiscal_year', 'state_name', 'member_number', 'age', 'sex',
            'snap_affiliation_code', 'disability_indicator', 'working_indicator',
            'wages', 'self_employment_income', 'social_security', 'ssi',
            'unemployment', 'tanf', 'child_support', 'total_income'
        ]
        
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal='center')
        
        # Data rows - results is a list of tuples (member, state_name)
        for row_idx, (member, state_name) in enumerate(results, 2):
            for col_idx, col_name in enumerate(columns, 1):
                # Get state_name from the query result tuple
                if col_name == 'state_name':
                    value = state_name
                else:
                    value = getattr(member, col_name, None)
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        # Auto-size columns
        for col_idx in range(1, len(columns) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
    
    def _create_errors_sheet(self, wb: Workbook, fiscal_year: int = None, limit: int = None):
        """Create QC errors data sheet."""
        ws = wb.create_sheet("QC_Errors")
        ws.sheet_properties.tabColor = "FF0000"  # Red
        
        # Get global filter
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        current_filter = filter_manager.get_filter()
        
        # Query data - SELECT state_name directly from joined Household to avoid lazy loading
        query = self.db.query(
            QCError,
            Household.state_name
        ).join(
            Household,
            (QCError.case_id == Household.case_id) & 
            (QCError.fiscal_year == Household.fiscal_year)
        ).order_by(QCError.case_id, QCError.fiscal_year, QCError.error_number)
        
        # Apply global state filter
        if current_filter.state:
            query = query.filter(Household.state_name == current_filter.state)
        
        # Apply fiscal year filter
        if fiscal_year:
            query = query.filter(Household.fiscal_year == fiscal_year)
        elif current_filter.fiscal_year:
            query = query.filter(Household.fiscal_year == current_filter.fiscal_year)
        
        # Apply limit
        if limit:
            # Get distributed sample
            query = query.limit(limit)
        
        results = query.all()
        
        if not results:
            ws['A1'] = "No data available"
            return
        
        # Headers
        columns = [
            'case_id', 'fiscal_year', 'state_name', 'error_number', 'element_code', 'nature_code',
            'responsible_agency', 'error_amount', 'discovery_method',
            'verification_status', 'occurrence_date', 'time_period', 'error_finding'
        ]
        
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal='center')
        
        # Data rows - results is a list of tuples (error, state_name)
        for row_idx, (error, state_name) in enumerate(results, 2):
            for col_idx, col_name in enumerate(columns, 1):
                # Get state_name from the query result tuple
                if col_name == 'state_name':
                    value = state_name
                else:
                    value = getattr(error, col_name, None)
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        # Auto-size columns
        for col_idx in range(1, len(columns) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
