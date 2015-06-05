'use strict';
angular
  .module('crosswatch')
  .config(function ($provide, $translateProvider) {

    var translationList = [
      {key: 'en', language: 'English', usecases: ['en_US', 'en_GB']},
      {key: 'de', language: 'Deutsch', usecases: ['de_DE', 'de_CH']},
      {key: 'pt', language: 'português', usecases: ['pt_BR']}
    ];

    var availableLangs = [];
    var mappings = {};
    // I know it's ugly, but javascript
    for (var i = 0; i < translationList.length; i++) {
      availableLangs.push(translationList[i].key);
      if (translationList[i].hasOwnProperty('usescases')) {
        for (var j = 0; j < translationList[i].usecases.length; j++) {
          mappings[translationList[i].usecases[j]] = translationList[i].key;
        }
      }
    }

    $provide.constant('translationList', translationList);

    // translation config
    $translateProvider
      .useSanitizeValueStrategy('sanitizeParameters')
      .useStorage('translateStorage')
      .addInterpolation('customInterpolation')
      .useStaticFilesLoader({
        prefix: 'i18n/locale-',
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
    string = string.replace(/(<([a-z\-]*)\s?[^>]*?>)/g, "$1</$2>");
    interpolationParams = interpolationParams || {};
    interpolationParams = $translateSanitization.sanitize(interpolationParams, 'params');

    var interpolatedText = $interpolate(string)(interpolationParams);
    interpolatedText = $translateSanitization.sanitize(interpolatedText, 'text');

    return interpolatedText;
  };

  return $translateInterpolator;
}
