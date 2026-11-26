"""O'rnatilgan shablonlar: har biri odatiy hujjatlar ro'yxati bilan (uz / ru / en)."""


def _i(uz, ru, en):
    return {"uz": uz, "ru": ru, "en": en}


BUILTIN_TEMPLATES = {
    "president": {
        "name": _i("Prezident stipendiyasi", "Президентская стипендия", "President scholarship"),
        "items": [
            _i("Ariza (rektor nomiga)", "Заявление (на имя ректора)", "Application letter (to the rector)"),
            _i("Ma'lumotnoma (obyektivka) va foto 3x4", "Объективка и фото 3x4", "Personal record (obyektivka) and 3x4 photo"),
            _i("CV (rezyume)", "CV (резюме)", "CV (résumé)"),
            _i("Pasport nusxasi", "Копия паспорта", "Passport copy"),
            _i("Diplom va ilovasi nusxalari", "Копии диплома и приложения", "Copies of diploma and transcript"),
            _i("Ilmiy ishlar ro'yxati (tasdiqlangan)", "Список научных трудов (заверенный)", "List of publications (certified)"),
            _i("Maqolalar nusxalari", "Копии статей", "Copies of articles"),
            _i("Ilmiy rahbar tavsiyanomasi", "Рекомендация научного руководителя", "Supervisor's recommendation"),
            _i("Kafedra yig'ilishi bayonnomasidan ko'chirma", "Выписка из протокола заседания кафедры", "Extract from the department meeting minutes"),
            _i("Ilmiy kengash qarori", "Решение учёного совета", "Academic council decision"),
            _i("Chet tili sertifikati (IELTS) nusxasi", "Копия сертификата по иностранному языку (IELTS)", "Foreign language certificate (IELTS) copy"),
            _i("Ilmiy tadqiqot rejasi / insho", "План научного исследования / эссе", "Research plan / essay"),
            _i("Yutuqlar (diplom, sertifikat, patent) nusxalari", "Копии достижений (дипломы, сертификаты, патенты)", "Copies of awards, certificates, patents"),
        ],
    },
    "grant": {
        "name": _i("Ilmiy grant", "Научный грант", "Research grant"),
        "items": [
            _i("Loyiha arizasi (shakl)", "Заявка на проект (форма)", "Project application form"),
            _i("Loyiha annotatsiyasi", "Аннотация проекта", "Project abstract"),
            _i("Loyiha tavsifi va ish rejasi", "Описание проекта и план работ", "Project description and work plan"),
            _i("Smeta (byudjet) hisob-kitobi", "Смета (бюджет) проекта", "Budget estimate"),
            _i("Loyiha rahbari va ijrochilar CV", "CV руководителя и исполнителей", "CVs of the PI and team members"),
            _i("Tashkilot kafolat xati", "Гарантийное письмо организации", "Letter of guarantee from the institution"),
            _i("Oldingi natijalar va nashrlar ro'yxati", "Предыдущие результаты и список публикаций", "Previous results and publications"),
            _i("Hamkor tashkilot roziligi", "Согласие организации-партнёра", "Partner organisation consent"),
            _i("Ekspert xulosasi / taqriz", "Экспертное заключение / рецензия", "Expert opinion / review"),
            _i("Kutilayotgan natijalar va tatbiq rejasi", "Ожидаемые результаты и план внедрения", "Expected results and implementation plan"),
        ],
    },
    "conference": {
        "name": _i("Konferensiya maqolasi", "Статья на конференцию", "Conference paper"),
        "items": [
            _i("Maqola matni (talablarga mos)", "Текст статьи (по требованиям)", "Paper text (per template)"),
            _i("Annotatsiya (3 tilda)", "Аннотация (на 3 языках)", "Abstract (in 3 languages)"),
            _i("Kalit so'zlar", "Ключевые слова", "Keywords"),
            _i("Mualliflar haqida ma'lumot", "Сведения об авторах", "Author information"),
            _i("Antiplagiat ma'lumotnomasi", "Справка об антиплагиате", "Plagiarism check report"),
            _i("Ro'yxatdan o'tish shakli", "Регистрационная форма", "Registration form"),
            _i("To'lov kvitansiyasi", "Квитанция об оплате", "Payment receipt"),
            _i("Taqdimot (slaydlar)", "Презентация (слайды)", "Presentation slides"),
            _i("Ekspert xulosasi (eksport nazorati)", "Экспертное заключение (экспортный контроль)", "Expert clearance letter"),
        ],
    },
    "attestation": {
        "name": _i("Attestatsiya hujjatlari", "Документы для аттестации", "Attestation documents"),
        "items": [
            _i("Ariza", "Заявление", "Application"),
            _i("Ma'lumotnoma (obyektivka)", "Объективка", "Personal record (obyektivka)"),
            _i("Mehnat daftarchasidan ko'chirma", "Выписка из трудовой книжки", "Employment record extract"),
            _i("Ilmiy-pedagogik faoliyat hisoboti", "Отчёт о научно-педагогической деятельности", "Report on academic and teaching activity"),
            _i("Ilmiy va o'quv-uslubiy ishlar ro'yxati", "Список научных и учебно-методических трудов", "List of scientific and teaching works"),
            _i("Malaka oshirish sertifikatlari", "Сертификаты повышения квалификации", "Professional development certificates"),
            _i("Ochiq dars tahlillari", "Анализы открытых занятий", "Open lesson evaluations"),
            _i("Kafedra xulosasi", "Заключение кафедры", "Department conclusion"),
            _i("Fakultet kengashi qarori", "Решение совета факультета", "Faculty council decision"),
            _i("Diplom nusxalari", "Копии дипломов", "Copies of diplomas"),
        ],
    },
    "abroad": {
        "name": _i("Xorijga hujjat", "Документы для выезда за рубеж", "Travel abroad documents"),
        "items": [
            _i("Xorijga chiqish pasporti", "Заграничный паспорт", "International passport"),
            _i("Taklifnoma", "Приглашение", "Invitation letter"),
            _i("Viza anketasi", "Визовая анкета", "Visa application form"),
            _i("Foto (viza talabiga mos)", "Фото (по требованиям визы)", "Photo (visa requirements)"),
            _i("Tibbiy sug'urta polisi", "Полис медицинского страхования", "Medical insurance policy"),
            _i("Bank ma'lumotnomasi (hisob qoldig'i)", "Справка из банка (остаток на счёте)", "Bank statement"),
            _i("Ish joyidan ma'lumotnoma", "Справка с места работы", "Employment certificate"),
            _i("Diplom apostili", "Апостиль на диплом", "Diploma apostille"),
            _i("Tarjimalar va notarial tasdiq", "Переводы и нотариальное заверение", "Translations and notarisation"),
            _i("Aviachipta va mehmonxona broni", "Авиабилет и бронь гостиницы", "Flight ticket and hotel booking"),
            _i("Buyruq (xizmat safari)", "Приказ (командировка)", "Order (business trip)"),
        ],
    },
}
