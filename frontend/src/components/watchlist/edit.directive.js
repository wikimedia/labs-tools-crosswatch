angular
  .module('crosswatch')
  .directive('watchlistEdit', watchlistEdit);

function watchlistEdit() {
  var directive = {
    link: link,
    scope: true,
    templateUrl: function(elem, attr){
      return 'components/watchlist/edit_' + attr.type + '.directive.html';
    },
    restrict: 'E'
  };
  return directive;

  function link(scope, element, attrs, ctrl) {
    var byte_change = scope.event.newlen - scope.event.oldlen;
    scope.event.bytes = numberFormat(byte_change);
    scope.event.bytestyle = byteStyle(byte_change);
    scope.event.titlestyle = titleStyle(scope.event.notificationtimestamp);

    /**
     * Formats the string for the number of changed bytes in a edit.
     * @param x
     * @returns human readable number
     */
    function numberFormat (x) {
      var result = x.toLocaleString();
      if (x > 0) {
        result = '+' + result;
      }
      return result;
    }

    /**
     * Get span class name from the number of changed bytes in a edit.
     * @param byte_change
     * @returns span class name
     */
    function byteStyle (byte_change) {
      var result;
      if (byte_change <= -500) {
        result = 'text-danger strong';
      } else if (byte_change < 0) {
        result = 'text-danger';
      } else if (byte_change === 0) {
        result = 'text-muted';
      } else if (byte_change >= 500) {
        result = 'text-success strong';
      } else { // 0 < byte_change <= 500
        result = 'text-success';
      }
      return result;
    }

    /**
     * Returns style for the page title based on the notificationtimestamp
     * @param timestamp
     * @returns {*}
     */
    function titleStyle (timestamp) {
      if (timestamp) {
        return 'mw-title';
      } else {
        return '';
      }
    }
  }
}
