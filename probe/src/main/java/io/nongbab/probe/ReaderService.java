package io.nongbab.probe;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * '기록 중'일 때만, 화면이 바뀔 때마다 보이는 글자·버튼 구조를 적어 둡니다.
 * - 비밀번호 칸과 입력 칸의 내용, 숫자 한 개짜리 키 누름은 기록하지 않습니다.
 * - 같은 화면은 한 번만 적습니다.
 */
public class ReaderService extends AccessibilityService {
    static volatile boolean recording = false;
    static volatile long stopAt = 0;
    static final StringBuilder log = new StringBuilder();
    static final Set<Integer> seen = new HashSet<>();
    static volatile int snapshots = 0;
    static volatile boolean connected = false;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable snap = this::snapshot;

    static synchronized void start(long millis, String note) {
        log.setLength(0);
        seen.clear();
        snapshots = 0;
        log.append("# 농밥 화면기록 ").append(now()).append('\n').append(note).append("\n\n");
        stopAt = System.currentTimeMillis() + millis;
        recording = true;
    }

    static synchronized void stop() { recording = false; }

    static String now() { return new SimpleDateFormat("MM-dd HH:mm:ss", Locale.KOREA).format(new Date()); }

    @Override
    protected void onServiceConnected() { connected = true; }

    @Override
    public boolean onUnbind(android.content.Intent intent) { connected = false; return super.onUnbind(intent); }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent e) {
        if (!recording) return;
        if (System.currentTimeMillis() > stopAt) { stop(); return; }
        CharSequence pkg = e.getPackageName();
        if (pkg == null || skipPackage(pkg.toString())) return;

        if (e.getEventType() == AccessibilityEvent.TYPE_VIEW_CLICKED) {
            String what = label(e.getSource());
            if (what.matches("^\\s*\\d\\s*$") || e.isPassword()) what = "(숫자키·비밀번호 - 기록 안 함)";
            synchronized (ReaderService.class) {
                log.append("▶ ").append(now()).append(" 누름: ").append(what).append(" [").append(pkg).append("]\n");
            }
        }
        handler.removeCallbacks(snap);           // 화면이 다 그려진 뒤 한 번만
        handler.postDelayed(snap, 800);
    }

    private boolean skipPackage(String p) {
        return p.equals(getPackageName()) || p.startsWith("com.android.systemui")
                || p.contains("launcher") || p.contains("inputmethod") || p.contains("honeyboard")
                || p.contains("keyboard");
    }

    private void snapshot() {
        if (!recording) return;
        StringBuilder sb = new StringBuilder();
        try {
            List<AccessibilityWindowInfo> wins = getWindows();
            for (AccessibilityWindowInfo w : wins) {
                if (w.getType() == AccessibilityWindowInfo.TYPE_INPUT_METHOD
                        || w.getType() == AccessibilityWindowInfo.TYPE_SYSTEM) continue;
                AccessibilityNodeInfo root = w.getRoot();
                if (root == null || root.getPackageName() == null || skipPackage(root.getPackageName().toString())) continue;
                sb.append("== 창: ").append(root.getPackageName()).append(" / ").append(w.getTitle()).append('\n');
                dump(root, 0, sb);
            }
        } catch (Exception ex) {
            sb.append("(읽기 실패: ").append(ex).append(")\n");
        }
        String s = sb.toString();
        if (s.isEmpty()) s = "(읽을 수 있는 글자가 없음 — 이 화면은 접근성으로 읽히지 않음)\n";
        synchronized (ReaderService.class) {
            if (!seen.add(s.hashCode())) return;
            snapshots++;
            log.append("\n----- 화면 ").append(snapshots).append(" (").append(now()).append(") -----\n").append(s);
            if (log.length() > 3_000_000) stop();  // 너무 길면 멈춤
        }
    }

    private void dump(AccessibilityNodeInfo n, int depth, StringBuilder sb) {
        if (n == null || depth > 60) return;
        String cls = n.getClassName() == null ? "?" : n.getClassName().toString();
        cls = cls.substring(cls.lastIndexOf('.') + 1);
        boolean secret = n.isPassword() || cls.contains("EditText");
        String text = n.getText() == null ? "" : n.getText().toString().replace('\n', '⏎');
        String desc = n.getContentDescription() == null ? "" : n.getContentDescription().toString().replace('\n', '⏎');
        String id = n.getViewIdResourceName() == null ? "" : n.getViewIdResourceName();
        id = id.substring(id.indexOf('/') + 1);
        boolean interesting = !text.isEmpty() || !desc.isEmpty() || n.isClickable() || n.isScrollable()
                || cls.contains("WebView") || !id.isEmpty();
        if (interesting) {
            Rect r = new Rect();
            n.getBoundsInScreen(r);
            for (int i = 0; i < depth; i++) sb.append(' ');
            sb.append(cls);
            if (!id.isEmpty()) sb.append(" #").append(id);
            if (secret) sb.append(" [입력칸-내용 기록 안 함]");
            else {
                if (!text.isEmpty()) sb.append(" \"").append(text).append('"');
                if (!desc.isEmpty() && !desc.equals(text)) sb.append(" (설명:").append(desc).append(')');
            }
            if (n.isClickable()) sb.append(" [누름]");
            if (n.isScrollable()) sb.append(" [스크롤]");
            if (n.isSelected() || n.isChecked()) sb.append(" [선택됨]");
            sb.append(" @").append(r.left).append(',').append(r.top).append('-').append(r.right).append(',').append(r.bottom).append('\n');
        }
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo c = n.getChild(i);
            dump(c, depth + 1, sb);
        }
    }

    private static String label(AccessibilityNodeInfo n) {
        if (n == null) return "?";
        if (n.isPassword()) return "";
        String t = n.getText() != null ? n.getText().toString() : "";
        if (t.isEmpty() && n.getContentDescription() != null) t = n.getContentDescription().toString();
        if (t.isEmpty() && n.getViewIdResourceName() != null) t = "#" + n.getViewIdResourceName();
        return t.replace('\n', ' ');
    }

    @Override
    public void onInterrupt() {}
}
