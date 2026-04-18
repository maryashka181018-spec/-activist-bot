const { Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle } = require('docx');
const fs = require('fs');

const args = JSON.parse(process.argv[2]);
// args: { events: [{title, date, location, students: ["Иванов Иван 33 ИСП", ...]}] }

function makeSection(ev) {
  const studentLines = ev.students.map(s =>
    new Paragraph({
      children: [new TextRun({ text: s, font: "Times New Roman", size: 24 })],
    })
  );

  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ", font: "Times New Roman", size: 24, bold: true })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "РЕСПУБЛИКИ ДАГЕСТАН", font: "Times New Roman", size: 24, bold: true })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "ГОСУДАРСТВЕННОЕ БЮДЖЕТНОЕ ПРОФЕССИОНАЛЬНОЕ ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ РЕСПУБЛИКИ ДАГЕСТАН", font: "Times New Roman", size: 24, bold: true })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "«ТЕХНИЧЕСКИЙ КОЛЛЕДЖ ИМЕНИ Р.Н. АШУРАЛИЕВА»", font: "Times New Roman", size: 24, bold: true })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "(ГБПОУ РД «ТК им. Р.Н. Ашуралиева»)", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "367013, г. Махачкала, Студенческий переулок, 3, тел.: (8722)68-16-04, e-mail: rpk-05@mail.ru,  http://www.therpk.ru", font: "Times New Roman", size: 20 })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "СПРАВКА-ПОДТВЕРЖДЕНИЕ", font: "Times New Roman", size: 24, bold: true })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      children: [new TextRun({
        text: `В рамках мероприятия медиа-направления «Профессионалитет», проведенного ${ev.date} в ${ev.location} обучающиеся:`,
        font: "Times New Roman", size: 24
      })]
    }),
    ...studentLines,
    new Paragraph({
      children: [new TextRun({ text: "в указанный период отсутствовали на учебных занятиях по уважительной причине в связи с участием в мероприятии.", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      children: [new TextRun({ text: "Справка выдана для предоставления кураторам и преподавателям.", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      children: [new TextRun({ text: "Директор                                                                       Рахманова М.М.", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({ children: [new TextRun({ text: "" })] }),
    new Paragraph({
      children: [new TextRun({ text: "Исполнитель: Магомедова М.Д.", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({
      children: [new TextRun({ text: "8-928-055-90-38", font: "Times New Roman", size: 24 })]
    }),
    new Paragraph({ pageBreakBefore: true, children: [new TextRun("")] }),
  ];
}

const allSections = args.events.flatMap(makeSection);

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1134, right: 850, bottom: 1134, left: 1701 }
      }
    },
    children: allSections
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(process.argv[3], buf);
  console.log("OK");
});
