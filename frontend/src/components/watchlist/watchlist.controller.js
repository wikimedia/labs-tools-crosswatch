'use strict';

angular.module('crosswatch')
  .controller('WatchlistCtrl', function ($log, dataService) {
    var vm = this;
    vm.icons = dataService.icons;
    vm.flagurl = dataService.flagurl;
    vm.watchlist = dataService.watchlist;
    vm.config = dataService.config;
    vm.moreWatchlistEntries = dataService.moreWatchlistEntries;

    vm.search = function (text) {
      dataService.filterWatchlist(text);
    };

    vm.clicked = function (event) {
      if ((event.type === 'edit') && !event.diff) {
        dataService.getDiff(event).then(function (diff) {
          event.diff = diff;
        })
      }
    };
  });
