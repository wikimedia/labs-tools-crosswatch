'use strict';

angular.module('crosswatch')
  .controller('SettingsCtrl', function ($translate, $log, dataService, $rootScope) {
    var vm = this;
    vm.config = dataService.config;
    vm.saveConfig = function () {
      dataService.saveConfig();
      dataService.filterWatchlist();
    };

    updatePeriodList();
    updateNamespaceList();
    $rootScope.$on('$translateChangeSuccess', function () {
      updatePeriodList();
      updateNamespaceList();
    });

    function updatePeriodList () {
      var hours = [0.5, 1, 1.5];
      var days = [2, 3, 7, 14, 21, 30];

      vm.periodList = [];
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
        vm.namespacesList = [];
        for (var i=0; i<list.length; i++) {
          vm.namespacesList.push({value: list[i], label: translations[translateStrings[i]]});
        }
      })
    }

    vm.resetWatchlist = function () {
      $log.info('resetting watchlist');
      dataService.resetWatchlist();
    };
  });
