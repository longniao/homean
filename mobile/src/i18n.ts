import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './locales/en';

const i18n = createInstance();
void i18n.use(initReactI18next).init({
  compatibilityJSON: 'v4',
  lng: 'en', fallbackLng: 'en', resources: { en: { translation: en } },
  interpolation: { escapeValue: false },
});

export default i18n;
