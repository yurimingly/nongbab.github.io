package io.nongbab.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 농밥 화면을 전체 화면으로 띄웁니다.
 * 인터넷이 되면 온라인 화면(GitHub Pages)을 열어 화면·식단이 항상 최신이고,
 * 안 되면 앱 안에 담긴 화면과 마지막 식단(docs/ 사본)을 엽니다.
 */
public class MainActivity extends Activity {
    private static final String LOCAL = "file:///android_asset/index.html";
    private WebView web;
    private String remote;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        remote = getString(R.string.web_url).trim();

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // 끼니 필터 기억
        web.addJavascriptInterface(new Bridge(getString(R.string.refresh_token).trim(),
                getString(R.string.repo).trim()), "NongbabApp");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if ("file".equals(u.getScheme()) || (!remote.isEmpty() && u.toString().startsWith(remote))) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u)); // 바깥 링크는 브라우저로
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                // 온라인 화면을 못 열면(오프라인 등) 앱 속 화면으로
                if (req.isForMainFrame() && !req.getUrl().toString().startsWith("file:")) view.loadUrl(LOCAL);
            }
        });

        setContentView(web);
        if (state == null || web.restoreState(state) == null) web.loadUrl(remote.isEmpty() ? LOCAL : remote);
    }

    /** 화면의 '지금 새 식단 확인' 버튼 → GitHub Actions의 식단 수집 봇을 바로 실행 */
    static class Bridge {
        private final String token, repo;

        Bridge(String token, String repo) { this.token = token; this.repo = repo; }

        @JavascriptInterface
        public boolean canRefresh() { return !token.isEmpty() && !repo.isEmpty(); }

        @JavascriptInterface
        public String refresh() {   // 화면 스크립트 전용 스레드에서 불리므로 네트워크 사용 가능
            if (!canRefresh()) return result(false, "이 앱에는 실행 권한이 설정되지 않았어요.");
            HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) new URL("https://api.github.com/repos/" + repo
                        + "/actions/workflows/nongbab.yml/dispatches").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(15000);
                c.setReadTimeout(15000);
                c.setDoOutput(true);
                c.setRequestProperty("Authorization", "Bearer " + token);
                c.setRequestProperty("Accept", "application/vnd.github+json");
                c.setRequestProperty("Content-Type", "application/json");
                try (OutputStream o = c.getOutputStream()) {
                    o.write("{\"ref\":\"main\"}".getBytes(StandardCharsets.UTF_8));
                }
                int code = c.getResponseCode();
                if (code == 204) return result(true, "");
                if (code == 401 || code == 403) return result(false, "실행 권한이 만료됐거나 잘못됐어요 (" + code + "). 토큰을 다시 만들어 주세요.");
                return result(false, "실행하지 못했어요 (" + code + ").");
            } catch (Exception e) {
                return result(false, "인터넷 연결을 확인해 주세요.");
            } finally {
                if (c != null) c.disconnect();
            }
        }

        private static String result(boolean ok, String msg) {
            return "{\"ok\":" + ok + ",\"message\":\"" + msg.replace("\\", "\\\\").replace("\"", "\\\"") + "\"}";
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
