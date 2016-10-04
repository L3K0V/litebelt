import re
import gspread
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials

GENADY_CREDENTIALS = getattr(settings, 'GEANDY_GDRIVE_AUTH_FILE', None)


class HeadquartersHelper(object):
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GENADY_CREDENTIALS, scope)
        self.gs = gspread.authorize(credentials)
        self.headquarters = self.gs.open_by_key('1o_8yzlr0hCjZ4iA_ccmDRPTCv1o6bBsA47GOy9ER5gI')

    def select_worksheet(self, name=None):
        if not name:
            self.worksheet = self.headquarters.sheet1
        self.worksheet = self.headquarters.worksheet(name)

    def get_student_homework(self, name, hw):

        if not self.worksheet:
            raise ValueError('You must select working sheet before operating')

        homework = self.worksheet.find('H{}'.format(hw))
        student = self.worksheet.find(name)

        cell = self.worksheet.cell(student.row, homework.col)

        return (cell.value, cell.numeric_value, cell.input_value)

    def update_student_homework(self, name, hw, value):
        if not self.worksheet:
            raise ValueError('You must select working sheet before operating')

        homework = self.worksheet.find('H{}'.format(hw))
        student = self.worksheet.find(name)

        cell = self.worksheet.update_cell(student.row, homework.col, value)

        return (cell.value, cell.numeric_value, cell.input_value)

    @staticmethod
    def formula_to_points(f):
        return list(map(int, ' '.join(re.split('=|\+', f)).split()))

    @staticmethod
    def points_to_formula(p):
        return '={}'.format('+'.join(list(map(str, p))))
