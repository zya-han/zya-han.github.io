/**
 * Dark mode toggle for zyahan.blog
 * - localStorage로 사용자 선택 기억
 * - prefers-color-scheme으로 OS 설정 자동 감지
 * - 페이지 로드 시 FOUC(깜빡임) 방지
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'zyahan-theme';

  /**
   * 저장된 테마가 없으면 OS 설정을 따름
   */
  function getPreferredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    // OS 다크 모드 감지
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  /**
   * 테마 적용
   */
  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }

  /**
   * 전환 애니메이션 트리거
   */
  function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = (current === 'dark') ? 'light' : 'dark';

    // 부드러운 전환 클래스 추가
    document.documentElement.classList.add('theme-transition');
    applyTheme(next);
    localStorage.setItem(STORAGE_KEY, next);

    // 전환 완료 후 클래스 제거 (성능)
    setTimeout(function () {
      document.documentElement.classList.remove('theme-transition');
    }, 350);
  }

  // 페이지 로드 즉시 테마 적용 (FOUC 방지)
  applyTheme(getPreferredTheme());

  // DOM 로드 후 버튼 이벤트 연결
  document.addEventListener('DOMContentLoaded', function () {
    var buttons = document.querySelectorAll('.theme-toggle');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', toggleTheme);
    });
  });

  // OS 테마 변경 실시간 감지 (사용자가 수동 선택하지 않았을 때만)
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
      // 사용자가 수동으로 설정한 적 없으면 OS 따라감
      if (!localStorage.getItem(STORAGE_KEY)) {
        applyTheme(e.matches ? 'dark' : 'light');
      }
    });
  }

})();
