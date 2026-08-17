#include "utils/mouse_tracker.h"

#include <QEvent>
#include <QMetaObject>

MouseHoverEventFilter::MouseHoverEventFilter(bool debugEnabled, QObject* parent)
    : QObject(parent)
    , m_debugEnabled(debugEnabled)
{
}

bool MouseHoverEventFilter::eventFilter(QObject* watched, QEvent* event)
{
    if (!m_debugEnabled)
        return false;

    if (event->type() == QEvent::Enter) {
        const QString objName = watched->objectName().isEmpty()
                                    ? QStringLiteral("未命名")
                                    : watched->objectName();
        const QString className = QString::fromLatin1(watched->metaObject()->className());

        static const char* ignoreClasses[] = {
            "QGraphicsOpacityEffect", "QGraphicsEffectSource", "QWidget",
        };
        for (const char* c : ignoreClasses) {
            if (className == QLatin1String(c))
                return false;
        }

        if (m_lastHoveredWidget != watched) {
            m_lastHoveredWidget = watched;
            qInfo("[mouse] 进入: %ls (%ls)",
                  reinterpret_cast<const wchar_t*>(objName.utf16()),
                  reinterpret_cast<const wchar_t*>(className.utf16()));
        }
    }
    return false;
}
