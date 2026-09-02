from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel

from pages.base_page import BasePage
from widgets.core_button import CoreButton
from widgets.text_editor import RoundedTextEdit

from resources.svgs import note_icon
from core.colors import NEUTRAL_1, NEUTRAL_4, COLOR_DANGER
from resources.constants import get_data_file_path


class NotePage(BasePage):
    """便笺页：随手记录的备忘 sticky note。

    内容自动保存到本地文件（防抖写盘），重启应用后不丢失；
    退出页面不清空内容（便笺的生命周期跨越页面切换与应用重启）。
    """

    PAGE_NAME = "note"
    TITLE = "Notes"
    MODULE_NAME = "Notes"
    MODULE_ICON = note_icon

    # 自动保存防抖间隔（毫秒）：停止输入一段时间后才写盘，避免每次按键都做文件 IO
    SAVE_DEBOUNCE_MS = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_size = (400, 300)

        # 便笺数据文件：开发目录放在项目根目录，打包环境放在 %APPDATA%（与配置文件同目录）
        self.note_file = get_data_file_path('notes.txt')

        # 防抖保存定时器：textChanged 触发重启计时，超时后写盘
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(self.SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._save_note)

        # 载入阶段标志：初始化填充文本时不当作"用户编辑"，不进入保存流程
        self._loading = False

        layout = self.set_main_layout('v')
        assert layout is not None

        # 便笺编辑区（圆角深色背景，与翻译页输入框同款）
        self.note_editor = RoundedTextEdit(placeholder='Write something here...', bg_color=NEUTRAL_1, parent=self)
        font = QFont()
        font.setPointSize(12)
        self.note_editor.setFont(font)
        self.note_editor.textChanged.connect(self._on_text_changed)

        # 底部状态栏：保存状态 + 字数统计 + 清空按钮
        self.status_label = self._make_footer_label()
        self.char_count_label = self._make_footer_label()

        self.clear_btn = CoreButton('Clear', parent=self)
        self.clear_btn.setBgColor(COLOR_DANGER)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_note)

        self.footer_layout = QHBoxLayout()
        self.footer_layout.addWidget(self.status_label)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.char_count_label)
        self.footer_layout.addWidget(self.clear_btn)

        layout.addWidget(self.note_editor)
        layout.addLayout(self.footer_layout)

        self._load_note()

    def _make_footer_label(self) -> QLabel:
        """底部状态栏的灰色小字标签"""
        label = QLabel(self)
        label_font = label.font()
        label_font.setPixelSize(11)
        label.setFont(label_font)

        palette = label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, NEUTRAL_4)
        label.setPalette(palette)
        return label

    # ==================== 数据读写 ====================
    def _load_note(self):
        """启动时从磁盘载入便笺内容"""
        try:
            content = self.note_file.read_text(encoding='utf-8')
        except OSError:
            content = ''

        self._loading = True
        self.note_editor.setPlainText(content)
        self._loading = False
        self._refresh_char_count()

    def _save_note(self):
        """把编辑区内容写入磁盘，并刷新保存状态"""
        try:
            self.note_file.parent.mkdir(parents=True, exist_ok=True)
            self.note_file.write_text(self.note_editor.toPlainText(), encoding='utf-8')
            self.status_label.setText('Saved')
        except OSError as e:
            self.status_label.setText('Save failed')
            print(f"[NotePage] 便笺保存失败: {e}")

    def _flush_save(self):
        """立即落盘：防抖计时器还在跑时直接写盘，避免退出时丢失最后一次输入"""
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_note()

    # ==================== 交互逻辑 ====================
    def _on_text_changed(self):
        if self._loading:
            return
        self.status_label.setText('Saving...')
        self._refresh_char_count()
        self._save_timer.start()  # 重启计时实现防抖

    def _refresh_char_count(self):
        self.char_count_label.setText(f'{len(self.note_editor.toPlainText())} chars')

    def _clear_note(self):
        self.note_editor.clear()  # 触发 textChanged，自动进入防抖保存流程
        self.note_editor.setFocus()

    # ==================== 页面生命周期 ====================
    def on_show(self):
        """显示便笺时聚焦编辑区，光标移到末尾方便续写"""
        cursor = self.note_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.note_editor.setTextCursor(cursor)
        self.note_editor.setFocus()

    def clear_data(self):
        # 便笺内容需要跨会话保留：退出页面只做立即落盘，不清空编辑区
        self._flush_save()

    def hideEvent(self, event):
        # 页面被切走（含应用退出收尾）时立即落盘
        self._flush_save()
        super().hideEvent(event)
