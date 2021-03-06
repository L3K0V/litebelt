import re
import gspread
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials

GENADY_CREDENTIALS = getattr(settings, 'GEANDY_GDRIVE_AUTH_FILE', None)
GOOGLE_DRIVE_DOC_ID = getattr(settings, 'GOOGLE_DRIVE_DOC_ID', None)


class HeadquartersHelper(object):
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GENADY_CREDENTIALS, scope)
        self.gs = gspread.authorize(credentials)
        self.headquarters = self.gs.open_by_key(GOOGLE_DRIVE_DOC_ID)

    def select_worksheet(self, name=None):
        """
        Set selected worksheed as currently active, so you can operate over it.
        """
        if not name:
            self.worksheet = self.headquarters.sheet1
        self.worksheet = self.headquarters.worksheet(name)

    def get_student_homework(self, name, hw):
        """
        Get student's homework result

        Returns tuple of string value, numberic value and the formula value of
        homework for given student.
        """
        if not self.worksheet:
            raise ValueError('You must select working sheet before operating')

        homework = self.worksheet.find('H{}'.format(hw))
        student = self.worksheet.find(name)

        cell = self.worksheet.cell(student.row, homework.col)

        return (cell.value, cell.numeric_value, cell.input_value)

    def update_student_homework(self, name, hw, value):
        """
        Update students homework providing new cell value for the spreadsheets.
        Consider passing formula instead of value.
        """
        if not self.worksheet:
            raise ValueError('You must select working sheet before operating')

        homework = self.worksheet.find('H{}'.format(hw))
        student = self.worksheet.find(name)

        self.worksheet.update_cell(student.row, homework.col, value)

    @staticmethod
    def formula_to_points(f):
        """
        Converts formula in list of points.
        Example: '=2.5+5+10+1' will return [2.5, 5.0, 10.0, 1.0]
        """
        return list(map(float, ' '.join(re.split('=|\+', f)).split()))

    @staticmethod
    def points_to_formula(p):
        """
        Converts list of points to formula.
        Example: [3.5, 5, 10, 3] will return '=3.5+5.0+10.0+3.0'
        """
        return '={}'.format('+'.join(list(map(str, p))))
