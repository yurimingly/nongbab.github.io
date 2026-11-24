package io.nongbab.probe;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** 1) 접근성 켜기 → 2) 기록 시작 + NH With 열기 → 3) 기록 저장·보내기 */
public class MainActivity extends Activity {
    private TextView status;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Uri lastSaved;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        col.setPadding(pad, dp(36), pad, pad);
        col.setBackgroundColor(Color.parseColor("#F3F6F1"));

        TextView title = new TextView(this);
        title.setText("농밥 화면기록");
        title.setTextSize(26);
        title.setTextColor(Color.parseColor("#2F6B3A"));
        col.addView(title);

        TextView how = new TextView(this);
        how.setText("NH With '오늘뭐먹지' 화면 구조를 기록해서, 자동으로 메뉴를 가져올 순서를 짜는 데 씁니다.\n\n"
                + "① 접근성 켜기 → '설치된 앱'에서 '농밥 화면기록'을 켜 주세요.\n"
                + "② '기록 시작'을 누르면 NH With가 열립니다. 비밀번호를 넣고 오늘뭐먹지에 들어가서\n"
                + "    손해 → 은행 → 중앙회 → 생명 → 농협타워를 하나씩 누르고, 각 식단을 끝까지 내려 보세요.\n"
                + "    날짜(요일)를 넘기는 버튼이 있으면 한 번 눌러 주세요.\n"
                + "③ 다 했으면 이 앱으로 돌아와 '기록 저장·보내기'를 누르고 Claude 채팅에 첨부해 주세요.\n\n"
                + "비밀번호 칸·입력 칸 내용과 숫자 키 누름은 기록하지 않아요. 기록은 3분 뒤 자동으로 멈춥니다.");
        how.setTextSize(14.5f);
        how.setTextColor(Color.parseColor("#18231B"));
        how.setPadding(0, dp(12), 0, dp(16));
        col.addView(how);

        col.addView(button("① 접근성 켜기", v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))));
        col.addView(button("② 기록 시작하고 NH With 열기", v -> startRecording()));
        col.addView(button("③ 기록 저장·보내기", v -> saveAndShare()));

        status = new TextView(this);
        status.setTextSize(14);
        status.setTextColor(Color.parseColor("#5D6B60"));
        status.setPadding(0, dp(16), 0, 0);
        col.addView(status);

        ScrollView sv = new ScrollView(this);
        sv.addView(col);
        setContentView(sv);
        tick();
    }

    private Button button(String text, android.view.View.OnClickListener l) {
        Button btn = new Button(this);
        btn.setText(text);
        btn.setTextSize(16);
        btn.setAllCaps(false);
        btn.setOnClickListener(l);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(8);
        btn.setLayoutParams(lp);
        return btn;
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private void tick() {
        String s = "접근성: " + (ReaderService.connected ? "켜짐 ✓" : "꺼짐 — ①을 눌러 켜 주세요")
                + "\n기록: " + (ReaderService.recording ? "기록 중 (" + ReaderService.snapshots + "개 화면)" :
                (ReaderService.snapshots > 0 ? "멈춤 (" + ReaderService.snapshots + "개 화면 기록됨)" : "아직 없음"));
        if (lastSaved != null) s += "\n저장됨: 다운로드 폴더";
        status.setText(s);
        handler.postDelayed(this::tick, 1000);
    }

    /** 'With'가 들어간 NH 앱을 설치된 앱 목록에서 찾음 (패키지 이름을 몰라도 되게) */
    private ResolveInfo findNhWith() {
        Intent i = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> apps = getPackageManager().queryIntentActivities(i, 0);
        for (ResolveInfo r : apps) {
            String label = String.valueOf(r.loadLabel(getPackageManager())).replace(" ", "").toLowerCase();
            if (label.contains("nhwith") || (label.contains("with") && label.contains("nh"))) return r;
        }
        return null;
    }

    private void startRecording() {
        if (!ReaderService.connected) {
            status.setText("먼저 ① 접근성 켜기에서 '농밥 화면기록'을 켜 주세요.");
            return;
        }
        ResolveInfo nh = findNhWith();
        String note = "NH With: " + (nh == null ? "못 찾음" : nh.activityInfo.packageName + " / " + version(nh.activityInfo.packageName));
        ReaderService.start(3 * 60 * 1000, note);
        if (nh == null) {
            status.setText("NH With를 찾지 못했어요. 기록은 시작됐으니 직접 NH With를 열어 주세요.");
            return;
        }
        startActivity(getPackageManager().getLaunchIntentForPackage(nh.activityInfo.packageName));
    }

    private String version(String pkg) {
        try {
            PackageInfo p = getPackageManager().getPackageInfo(pkg, 0);
            return p.versionName;
        } catch (PackageManager.NameNotFoundException e) {
            return "?";
        }
    }

    private void saveAndShare() {
        ReaderService.stop();
        String text;
        synchronized (ReaderService.class) { text = ReaderService.log.toString(); }
        if (text.isEmpty()) {
            status.setText("아직 기록이 없어요. ②부터 해 주세요.");
            return;
        }
        try {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, "nongbab-screen-" + System.currentTimeMillis() + ".txt");
            v.put(MediaStore.Downloads.MIME_TYPE, "text/plain");
            v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            try (OutputStream o = getContentResolver().openOutputStream(uri)) {
                o.write(text.getBytes(StandardCharsets.UTF_8));
            }
            lastSaved = uri;
            Intent send = new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(send, "기록 보내기 (Claude 앱 선택)"));
        } catch (Exception e) {
            status.setText("저장 실패: " + e);
        }
    }
}
