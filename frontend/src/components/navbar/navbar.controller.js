'use strict';

angular.module('crosswatch')
  .controller('NavbarCtrl', function (translationList, $translate, $rootScope, authService, amMoment, localStorageService) {
    var vm = this;
    vm.langs = translationList;
    vm.selectedLang = $translate.use();
    vm.loggedin = authService.isloggedin();

    /**
     * Strange bug, $translate.use() is sometimes undefined if loaded by angular-translate from local storage
     */
    if (typeof vm.selectedLang === "undefined") {
      vm.selectedLang = localStorageService.get('NG_TRANSLATE_LANG_KEY');
    }

    $rootScope.$on('login', function (event, msg) {
      vm.user = msg;
      vm.loggedin = true;
    });

    vm.changeLanguage = function (langKey) {
      amMoment.changeLocale(langKey);
      $translate.use(langKey);
    };
  });
