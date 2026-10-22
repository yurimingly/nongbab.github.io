package io.nongbab.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

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
