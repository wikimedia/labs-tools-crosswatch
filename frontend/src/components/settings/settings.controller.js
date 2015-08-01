'use strict';

angular.module('crosswatch')
  .controller('SettingsCtrl', function ($translate, $log, dataService, $rootScope, debounce) {
    var vm = this;
    vm.config = dataService.config;
    vm.saveConfig = function () {
      dataService.saveConfig();
      dataService.filterWatchlist();
    };

    vm.namespacesList = [];
    vm.periodList = [];
    debounce(updatePeriodList, 50)();
    debounce(updateNamespaceList, 50)();
    $rootScope.$on('$translateChangeSuccess', function () {
      debounce(updatePeriodList, 50)();
      debounce(updateNamespaceList, 50)();
    });

    function updatePeriodList () {
      var hours = [0.5, 1, 1.5];
      var days = [2, 3, 7, 14, 21, 30];

      vm.periodList.length = 0;
      var addItem = function (value) {
        return function (label) {
          vm.periodList.push({value: value, label: label})
        }
      };
      for (var i=0; i<hours.length; i++) {
        $translate('SHOW_LAST_HOURS', {number: 24*hours[i]}).then(addItem(hours[i]));
      }
      for (var j=0; j<days.length; j++) {
        $translate('SHOW_LAST_DAYS', {number: days[j]}).then(addItem(days[j]));
      }
    }

    function updateNamespaceList () {
      var list = vm.config.namespacesList;
      var translateStrings = [];
      for (var i=0; i<list.length; i++) {
        translateStrings.push("NS_" + list[i]);
      }
      $translate(translateStrings).then(function (translations) {
        vm.namespacesList.length = 0;
        for (var i=0; i<list.length; i++) {
          vm.namespacesList.push({value: list[i], label: translations[translateStrings[i]]});
        }
      });
    }

    vm.resetWatchlist = function () {
      $log.info('resetting watchlist');
      dataService.resetWatchlist();
    };
  });
