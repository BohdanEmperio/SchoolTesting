from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout


class ClassDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Данные класса")
        layout = QVBoxLayout(self)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название (например, 10А)")
        
        # Если данные переданы (режим редактирования), заполняем поля
        if data:
            self.name_input.setText(data['name'])
            
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        
        layout.addWidget(QLabel("Введите название класса:"))
        layout.addWidget(self.name_input)
        layout.addWidget(save_btn)

    def get_data(self):
        return {"name": self.name_input.text()}