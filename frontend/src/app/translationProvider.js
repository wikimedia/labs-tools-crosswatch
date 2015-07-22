'use strict';
angular
  .module('crosswatch')
  .value('textDirection', {dir: 'ltr'}) // can be 'ltr' or 'rtl'
  .config(function ($translateProvider, translationList) {
    var availableLangs = [];
    var mappings = {};
    // Create list of language codes and mappings
    for (var i = 0; i < translationList.length; i++) {
      availableLangs.push(translationList[i].key);
      if (translationList[i].hasOwnProperty('usescases')) {
        for (var j = 0; j < translationList[i].usecases.length; j++) {
          mappings[translationList[i].usecases[j]] = translationList[i].key;
        }
      }
    }

    $translateProvider
      .useSanitizeValueStrategy('sanitizeParameters')
      .useStorage('translateStorage')
      .addInterpolation('customInterpolation')
      .useStaticFilesLoader({
        prefix: 'i18n/',
        suffix: '.json'
      })
      .registerAvailableLanguageKeys(availableLangs, mappings)
      .determinePreferredLanguage()
      .fallbackLanguage('en');
  })
  .factory('customInterpolation', customInterpolation);

/**
 * Custom translation interpolator who adds html closing tags to translation strings.
 * Based on https://github.com/angular-translate/angular-translate/blob/92bc9551279fc2f5bc7daaedebc87adede8b3713/src/service/default-interpolation.js
 */
function customInterpolation ($interpolate, $translateSanitization) {
  var $translateInterpolator = {},
    $locale,
    $identifier = 'custom';

  $translateInterpolator.setLocale = function (locale) {
    $locale = locale;
  };

  $translateInterpolator.getInterpolationIdentifier = function () {
    return $identifier;
  };

  $translateInterpolator.interpolate = function (string, interpolationParams) {
    /**
     * Closes html tags in translation strings (but not for <a> tags) and adds quotation marks.
     * For example: "<user> foo <user title={{bar|baz}}>" -> "<user></user> foo <user title=\"{{bar|baz}}\"></user>"
     */
    string = string.replace(/(<([a-z\-]{2,})\s?[^>]*?>)/g, "$1</$2>").replace(/({{[\w|]+}})>/g, "\"$1\">");
    interpolationParams = interpolationParams || {};
    interpolationParams = $translateSanitization.sanitize(interpolationParams, 'params');

    var interpolatedText = $interpolate(string)(interpolationParams);
    interpolatedText = $translateSanitization.sanitize(interpolatedText, 'text');

    return interpolatedText;
  };

  return $translateInterpolator;
}
