'use strict';

angular.module('crosswatch')
  .controller('NavbarCtrl', function (translationList, $translate, $rootScope, authService, amMoment) {
    var vm = this;
    vm.langs = translationList;
    vm.selectedLang = $translate.use();
    vm.loggedin = authService.isloggedin();

    $rootScope.$on('login', function (event, msg) {
      vm.user = msg;
      vm.loggedin = true;
    });

    vm.changeLanguage = function (langKey) {
      amMoment.changeLocale(langKey);
      $translate.use(langKey);
    };
  });
