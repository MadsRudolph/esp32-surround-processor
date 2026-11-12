idf_component_register(SRCS "dolby.c" INCLUDE_DIRS "include" PRIV_REQUIRES liba52)
target_compile_options(${COMPONENT_LIB} PRIVATE -O2)
