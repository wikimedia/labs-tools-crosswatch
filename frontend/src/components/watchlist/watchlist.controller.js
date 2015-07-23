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
      event.showDiff = !event.showDiff;

      if ((event.type === 'edit') && !event.diff) {
        vm.getDiff(event).then(function (diff) {
          event.diff = diff;
        })
      }
    };

    vm.watchPage = function (event, currentStatus) {
      var request = {
        action: 'watch',
        projecturl: event.projecturl,
        status: currentStatus,
        title: event.title
      };
      dataService.query(request).then(function (status) {
        // only change icon status if server gives no errors
        event.isUnwatched = !status;
      })
    };

    /**
     * Get diff for a watchlist edit event
     */
    vm.getDiff = function (event) {
      var request = {
        action: 'diff',
        projecturl: event.projecturl,
        old_revid: event.old_revid,
        revid: event.revid,
        pageid: event.pageid
      };
      return dataService.query(request);
    };
  });
