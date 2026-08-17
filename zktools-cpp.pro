QT       += core gui widgets svg network
CONFIG   += c++17

TARGET    = zktools
TEMPLATE  = app

# 与 Python 版 zktools 相同的目录结构
INCLUDEPATH += .

SOURCES += \
    main.cpp \
    core/hotkey_manager.cpp \
    core/page_animation.cpp \
    core/page_router.cpp \
    core/window_manager.cpp \
    pages/base_page.cpp \
    pages/clipboard_ctl_page.cpp \
    pages/homepage.cpp \
    pages/module_center_page.cpp \
    pages/note_page.cpp \
    pages/notify_page.cpp \
    pages/setting_page.cpp \
    pages/touchpad_ctl_page.cpp \
    pages/translator_page.cpp \
    resources/colors.cpp \
    resources/constants.cpp \
    resources/svgs.cpp \
    utils/clipboard_monitor.cpp \
    utils/mouse_tracker.cpp \
    utils/switch_touchpad.cpp \
    utils/text_manager.cpp \
    utils/translator.cpp \
    widgets/core_button.cpp \
    widgets/hover.cpp \
    widgets/main_container.cpp \
    widgets/svg_button.cpp \
    widgets/text_editor.cpp

HEADERS += \
    core/hotkey_manager.h \
    core/page_animation.h \
    core/page_router.h \
    core/window_manager.h \
    pages/i_page.h \
    pages/base_page.h \
    pages/clipboard_ctl_page.h \
    pages/homepage.h \
    pages/module_center_page.h \
    pages/note_page.h \
    pages/notify_page.h \
    pages/setting_page.h \
    pages/touchpad_ctl_page.h \
    pages/translator_page.h \
    resources/colors.h \
    resources/constants.h \
    resources/svgs.h \
    utils/clipboard_monitor.h \
    utils/mouse_tracker.h \
    utils/switch_touchpad.h \
    utils/text_manager.h \
    utils/translator.h \
    widgets/core_button.h \
    widgets/hover.h \
    widgets/main_container.h \
    widgets/svg_button.h \
    widgets/text_editor.h

win32 {
    # RegisterHotKey / SendInput / ShellExecuteW / COM / UI Automation
    # （MinGW 未附带 uiautomationcore 导入库，直接链接系统 DLL；
    #   COM GUID 定义在 libuuid，SysFreeString 在 oleaut32）
    LIBS += -lole32 -loleaut32 -luuid -luser32 -lshell32
    LIBS += $$system_path(C:/Windows/System32/UIAutomationCore.dll)
}
