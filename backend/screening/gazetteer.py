"""Word lists that tell people and places apart from skills and companies.

All entries are folded: lowercase, without accents. The entity recognizer is
small and noisy ("Kafka" is a person to it, "Kubernetes" a place), so a name or
a place is only trusted when these lists, or the context, agree.
"""


def words(text: str) -> frozenset[str]:
    return frozenset(text.split())


def _phrases(text: str) -> frozenset[str]:
    return frozenset(part.strip() for part in text.split(",") if part.strip())


GIVEN_NAMES = words(
    """
    aaron abigail adolfo adrian adriana agustin aida alan alba alberto alejandra alejandro alexa
    alexander alexis alfonso alfredo alicia alma alondra alvaro amanda amelia ana andrea andres
    angel angela angelica anna antonio araceli ariadna armando arturo aurora axel barbara beatriz
    benjamin berenice bernardo blanca brenda bruno camila carla carlos carmen carolina catalina
    cecilia cesar christian claudia cristian cristina cynthia dafne damian daniel daniela dante
    dario david diana diego dolores eduardo elena elias elisa elizabeth emilia emiliano emilio
    emily emma enrique erick erika ernesto esteban estefania esther eugenia eva fabian fabiola
    fatima federico felipe fernanda fernando francisco gabriel gabriela gael gerardo german
    gilberto gisela gloria graciela guadalupe guillermo gustavo hector hilda hugo ignacio irene
    iris irma isaac isabel isabella itzel ivan ivonne jacqueline jaime javier jazmin jesus jimena
    joaquin jorge jose josefina juan juana julia julian juliana julio karen karina karla laura
    leonardo leticia liliana lizbeth lorena lorenzo lourdes lucia luis luisa lupita manuel
    marcela marco marcos margarita maria mariana mariano mario marisol marta martha martin mateo
    matias mauricio maximiliano mayra melissa mercedes miguel miriam monica nadia natalia nayeli
    nicolas noemi norma octavio olga omar oscar pablo paola patricia paula paulina pedro rafael
    ramon raquel raul rebeca regina renata ricardo roberto rocio rodrigo rogelio rosa rosario
    ruben salvador samuel sandra santiago sara sebastian sergio silvia sofia sonia susana tania
    teresa tomas ulises valentina valeria vanessa veronica victor victoria viridiana ximena
    yolanda yesenia zoe
    adam alex alice amy andrew anthony ashley ben brian charles chris christopher dan edward
    eric george grace hannah henry jack james jane jason jennifer jessica john jonathan joseph
    joshua justin kate katherine kevin linda lisa mark mary matthew megan michael michelle mike
    nancy nathan nicholas olivia patrick paul peter rachel richard robert ryan samantha sarah
    scott stephanie steven susan thomas tim timothy tyler william
    """
)

PLACES = _phrases(
    # Mexican states
    "aguascalientes, baja california, baja california sur, campeche, chiapas, chihuahua,"
    "ciudad de mexico, coahuila, colima, durango, estado de mexico, guanajuato, guerrero,"
    "hidalgo, jalisco, michoacan, morelos, nayarit, nuevo leon, oaxaca, puebla, queretaro,"
    "quintana roo, san luis potosi, sinaloa, sonora, tabasco, tamaulipas, tlaxcala, veracruz,"
    "yucatan, zacatecas,"
    # Cities
    "acapulco, cancun, celaya, ciudad juarez, ciudad obregon, cdmx, cuernavaca, culiacan,"
    "ensenada, guadalajara, hermosillo, irapuato, la paz, leon, los cabos, mazatlan, merida,"
    "mexicali, monterrey, morelia, nezahualcoyotl, pachuca, playa del carmen,"
    "puerto vallarta, reynosa, saltillo, san pedro garza garcia, tampico, tepic, tijuana,"
    "tlalnepantla, tlaquepaque, toluca, torreon, tuxtla gutierrez, villahermosa, xalapa,"
    "zapopan, apodaca, guadalupe, san nicolas de los garza, santa catarina, escobedo,"
    "naucalpan, ecatepec, coyoacan, tlalpan, iztapalapa, polanco,"
    "bogota, medellin, cali, barranquilla, cartagena, lima, santiago, valparaiso,"
    "buenos aires, cordoba, rosario, montevideo, quito, guayaquil, caracas, la habana,"
    "san jose, san salvador, tegucigalpa, managua, santo domingo, san juan, madrid,"
    "barcelona, valencia, sevilla, new york, los angeles, san francisco, chicago, houston,"
    "austin, dallas, miami, seattle, boston, san diego, denver, atlanta, toronto, vancouver,"
    "montreal, london, paris, berlin, amsterdam, lisbon, dublin, sao paulo, rio de janeiro,"
    # Countries
    "mexico, estados unidos, united states, usa, canada, colombia, peru, chile, argentina,"
    "uruguay, paraguay, bolivia, ecuador, venezuela, cuba, costa rica, panama, guatemala,"
    "honduras, el salvador, nicaragua, republica dominicana, puerto rico, brasil, brazil,"
    "espana, spain, francia, france, alemania, germany, italia, italy, portugal, reino unido,"
    "united kingdom, inglaterra, england, irlanda, ireland, paises bajos, netherlands, india,"
    "china, japon, japan,"
    # US states
    "alabama, alaska, arizona, arkansas, california, colorado, connecticut, delaware, florida,"
    "georgia, hawaii, idaho, illinois, indiana, iowa, kansas, kentucky, louisiana, maine,"
    "maryland, massachusetts, michigan, minnesota, mississippi, missouri, montana, nebraska,"
    "nevada, new hampshire, new jersey, new mexico, north carolina, north dakota, ohio,"
    "oklahoma, oregon, pennsylvania, rhode island, south carolina, south dakota, tennessee,"
    "texas, utah, vermont, virginia, washington, west virginia, wisconsin, wyoming"
)

# Written abbreviations of states and countries, matched as written, after a comma:
# "Monterrey, NL", "Querétaro, Qro.", "Austin, TX".
REGION_ABBREVIATIONS = words(
    """
    Ags. BC BCS Camp. Chis. Chih. CDMX Coah. Col. Dgo. Edomex Gto. Gro. Hgo. Jal. Méx. Mich.
    Mor. Nay. NL N.L. Oax. Pue. Qro. Q.R. SLP S.L.P. Sin. Son. Tab. Tamps. Tlax. Ver. Yuc.
    Zac. AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV
    NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY USA EE.UU. EUA
    """
)

NATIONALITIES = words(
    """
    mexicano mexicana mexicanos mexicanas colombiano colombiana peruano peruana chileno chilena
    argentino argentina venezolano venezolana cubano cubana ecuatoriano ecuatoriana boliviano
    boliviana uruguayo uruguaya paraguayo paraguaya guatemalteco guatemalteca hondureno
    hondurena salvadoreno salvadorena nicaraguense costarricense panameno panamena dominicano
    dominicana puertorriqueno puertorriquena espanol espanola estadounidense canadiense
    brasileno brasilena frances francesa aleman alemana italiano italiana
    mexican colombian peruvian chilean argentinian argentine venezuelan cuban ecuadorian
    bolivian uruguayan guatemalan honduran salvadoran nicaraguan panamanian dominican spanish
    american canadian brazilian french german italian british
    """
)

# Words in job titles: "Director de Operaciones" is not a person.
TITLE_WORDS = words(
    """
    director directora gerente jefe jefa manager head lead lider coordinador coordinadora
    supervisor supervisora ingeniero ingeniera engineer analista analyst desarrollador
    desarrolladora developer disenador disenadora designer consultor consultora consultant
    especialista specialist vp ceo cto cfo coo president presidente presidenta socio socia
    partner senior junior sr jr licenciado licenciada licenciatura maestria doctor doctora
    scientist cientifico cientifica arquitecto arquitecta architect owner administrator
    administrador administradora tecnico tecnica technician programmer programador
    programadora intern becario becaria practicante backend frontend product producto
    operaciones operations proyectos projects
    """
)

# Words in company and school names: "Acme Industrial" is not a person.
ORG_WORDS = words(
    """
    grupo group industrial industrias corp corporation inc llc sa ltd company compania
    technologies tecnologias tecnologia labs consulting bank banco universidad university
    instituto institute school escuela colegio tecnologico fintech retail logistica manufactura
    digital software systems sistemas solutions soluciones agencia agency studio estudio
    partners holdings capital ventures foundation fundacion hospital clinica cloud data
    """
)
